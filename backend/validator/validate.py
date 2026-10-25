"""Independent plan validator (002 Spec §9; ENG-FR-07, ENG-FR-08).

validate(plan, request, dataset) -> list of failures, each "V-xx: message"; empty means valid.
It recomputes every time, cost and window from the dataset and config.yaml and trusts no field of the
plan. It imports only tripwise.data and tripwise.models, never solver code, so it can also check the
baseline planners of Feature 008.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import yaml

from tripwise.data import Dataset, round_half_up
from tripwise.models import Plan, TripRequest

CONFIG = Path(__file__).resolve().parents[1] / "tripwise" / "config.yaml"
TIERS = ("budget", "mid", "premium")


def _t(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


class _Check:
    def __init__(self, plan: Plan, req: TripRequest, ds: Dataset, cfg: dict):
        self.p, self.r, self.ds, self.c = plan, req, ds, cfg
        self.fail: list[str] = []
        self.P = req.people
        self.D = (req.end_date - req.start_date).days + 1
        lt_mode = cfg["local_mode"][req.prefs.comfort]
        self.local = ds.local.get((req.destination, lt_mode))
        self.lt_mode = lt_mode

    def err(self, code: str, msg: str) -> None:
        self.fail.append(f"{code}: {msg}")

    # --- recomputation helpers (independent of the solver) ---------------------------------
    def vehicles(self) -> int:
        return math.ceil(self.P / self.local.capacity)

    def ride(self, km: float) -> int:
        lt = self.local
        return round_half_up(lt.min_fare + lt.per_km * max(0.0, km - lt.min_km)) * self.vehicles()

    def journey(self, mode: str, cls: str) -> tuple[int | None, dict | None]:
        pair = self.ds.pairs.get((self.r.origin, self.r.destination))
        f = self.ds.fares.get((mode, cls))
        hub = self.ds.hubs.get((self.r.destination, mode))
        ohub = self.ds.hubs.get((self.r.origin, mode))
        if pair is None or f is None or hub is None or ohub is None or not pair.available.get(mode):
            return None, None
        km = pair.km[mode]
        fare = max(f.min_fare, round_half_up(f.base_fare + f.per_km * km))
        cost = self.P * fare + hub.access_cost * self.vehicles()
        info = {"minutes": pair.minutes[mode], "access": hub.access_minutes, "oaccess": ohub.access_minutes,
                "comfort": f.comfort_value}
        return cost, info

    def windows(self, out_mode: str, out_info: dict, ret_mode: str, ret_info: dict) -> list[dict]:
        c = self.c
        s = _t(c["day_start"])
        e = min(s + round(self.r.prefs.daily_hours_out * 60), _t(c["day_end_cap"]))
        om, rm = out_info["minutes"], ret_info["minutes"]
        o_night = out_mode != "flight" and om >= c["overnight_min_minutes"]
        r_night = ret_mode != "flight" and rm >= c["overnight_min_minutes"]
        if o_night:
            first = _t(c["overnight_arrive"]) + out_info["access"] + c["overnight_arrival_buffer_minutes"]
        else:
            dep = _t(c["flight_depart"] if out_mode == "flight" else c["surface_depart"])
            first = dep + om + out_info["access"] + c["arrival_buffer_minutes"]
        if r_night:
            last = _t(c["overnight_depart"]) - ret_info["access"] - c["departure_buffer_minutes"]
        else:
            over = c["flight_overhead_minutes"] if ret_mode == "flight" else 0
            last = _t(c["return_deadline"]) - (rm + ret_info["access"] + over) - c["departure_buffer_minutes"]
        lc = c["lunch"]
        pace = c["pace"][self.r.prefs.pace]
        out = []
        for d in range(1, self.D + 1):
            ws = max(s, first) if d == 1 else s
            we = min(e, last) if d == self.D else e
            we = max(ws, we)
            active = we - ws >= c["min_activity_window_minutes"]
            lstart = max(ws, _t(lc["earliest"]))
            lunch = (active and we - ws >= lc["min_window_h"] * 60 and lstart <= _t(lc["latest"])
                     and lstart + lc["minutes"] <= we)
            usable = math.floor((we - ws - (lc["minutes"] if lunch else 0)) * pace["fill"]) if active else 0
            out.append({"start": ws, "end": we, "active": active, "lunch": lunch, "usable": usable,
                        "max": pace["max"] if active else 0})
        return out

    # --- checks ---------------------------------------------------------------------------
    def run(self) -> list[str]:
        p, r, ds, c = self.p, self.r, self.ds, self.c
        if self.local is None:
            self.err("V-03", f"no {self.lt_mode} tariff for {r.destination}")
            return self.fail

        # V-01 request identity, dates, day count
        if p.request_hash != r.request_hash():
            self.err("V-01", "request_hash does not match the request")
        if len(p.days) != self.D:
            self.err("V-01", f"{len(p.days)} days, request has {self.D}")
        for i, d in enumerate(p.days):
            exp = r.start_date + timedelta(days=i)
            if d.day != i + 1 or d.date != exp.isoformat() or d.weekday != exp.weekday():
                self.err("V-01", f"day {i + 1} is {d.day} {d.date} weekday {d.weekday}, expected {exp}")

        # V-02 transport
        ob, rt = p.transport.outbound, p.transport.return_
        oc, oi = self.journey(ob.mode, ob.class_)
        rc, ri = self.journey(rt.mode, rt.class_)
        for name, j, cost, info in (("outbound", ob, oc, oi), ("return", rt, rc, ri)):
            if cost is None:
                self.err("V-02", f"{name} {j.mode} {j.class_} is not available for {r.origin}-{r.destination}")
                continue
            if r.prefs.modes.get(j.mode) == "avoid":
                self.err("V-02", f"{name} uses avoided mode {j.mode}")
            if j.mode != "flight" and info["minutes"] > c["max_surface_minutes"]:
                self.err("V-02", f"{name} {j.mode} takes {info['minutes']} min > {c['max_surface_minutes']}")
            night = j.mode != "flight" and info["minutes"] >= c["overnight_min_minutes"]
            door = info["oaccess"] + info["minutes"] + info["access"] + (c["flight_overhead_minutes"] if j.mode == "flight" else 0)
            if j.overnight != night or j.minutes != door:
                self.err("V-02", f"{name} overnight/minutes {j.overnight}/{j.minutes}, expected {night}/{door}")
        if oc is None or rc is None:
            return self.fail
        if ob.overnight:
            dep = (_t(c["overnight_arrive"]) - oi["minutes"]) % 1440
            arr = _t(c["overnight_arrive"]) + oi["access"]
        else:
            dep = _t(c["flight_depart"] if ob.mode == "flight" else c["surface_depart"])
            arr = dep + oi["minutes"] + oi["access"]
        if (_t(ob.depart), _t(ob.arrive_centre)) != (dep, arr):
            self.err("V-02", f"outbound times {ob.depart}/{ob.arrive_centre} do not match the timetable rule")
        if rt.overnight:
            lv = _t(c["overnight_depart"]) - ri["access"]
            ao = (_t(c["overnight_depart"]) + ri["minutes"]) % 1440
        else:
            over = c["flight_overhead_minutes"] if rt.mode == "flight" else 0
            lv = _t(c["return_deadline"]) - (ri["minutes"] + ri["access"] + over)
            ao = _t(c["return_deadline"])
        if (_t(rt.leave_centre), _t(rt.arrive_origin)) != (lv, ao):
            self.err("V-02", f"return times {rt.leave_centre}/{rt.arrive_origin} do not match the timetable rule")

        # V-13 hotel
        h = ds.hotels.get(p.hotel.hotel_id)
        tier = r.prefs.comfort
        ti = TIERS.index(tier)
        allowed = {tier}
        if p.variant == "experience" and ti < 2:
            allowed.add(TIERS[ti + 1])
        if p.variant == "saver" and ti > 0:
            allowed.add(TIERS[ti - 1])
        rooms = math.ceil(self.P / 2)
        if h is None or h.city_id != r.destination:
            self.err("V-13", f"hotel {p.hotel.hotel_id} is not in {r.destination}")
        else:
            if h.tier not in allowed or p.hotel.tier != h.tier:
                self.err("V-13", f"hotel tier {h.tier} not allowed for comfort {tier} ({p.variant or 'single plan'})")
            if p.hotel.nights != self.D - 1 or p.hotel.rooms != rooms or p.hotel.price_per_room_night != h.price:
                self.err("V-13", f"nights/rooms/price {p.hotel.nights}/{p.hotel.rooms}/{p.hotel.price_per_room_night}, "
                                 f"expected {self.D - 1}/{rooms}/{h.price}")

        # V-05 attractions
        ids = p.activity_ids()
        if len(ids) != len(set(ids)):
            self.err("V-05", "an attraction appears twice")
        for a in ids:
            at = ds.attractions.get(a)
            if at is None or at.city_id != r.destination:
                self.err("V-05", f"{a} is not an attraction of {r.destination}")
        if any("V-05" in f for f in self.fail) or h is None:
            return self.fail

        # V-12 locks and excludes
        for a in r.locks:
            if a not in ids:
                self.err("V-12", f"locked {a} is missing")
        for a in r.excludes:
            if a in ids:
                self.err("V-12", f"excluded {a} is present")

        wins = self.windows(ob.mode, oi, rt.mode, ri)
        hotel = h.hotel_id
        entry_total = local_total = 0
        for d, w in zip(p.days, wins):
            tag = f"day {d.day}"
            exp_window = [f"{w['start'] // 60:02d}:{w['start'] % 60:02d}", f"{w['end'] // 60:02d}:{w['end'] % 60:02d}"] \
                if w["active"] else None
            # V-09 the window itself and first/last times
            if d.window != exp_window:
                self.err("V-09", f"{tag} window {d.window}, expected {exp_window}")
            if d.stops and not w["active"]:
                self.err("V-09", f"{tag} has stops but no usable window")
            # V-11 lunch on exactly the right days
            if w["lunch"] != (d.lunch is not None):
                self.err("V-11", f"{tag} lunch {'missing' if w['lunch'] else 'not allowed'}")
            busy: list[tuple[int, int]] = []
            prev, prev_end = hotel, None
            for s in d.stops:
                at = ds.attractions[s.attraction_id]
                arrive, start, end = _t(s.arrive), _t(s.start), _t(s.end)
                leg = s.leg_from_prev
                km, mins = ds.travel(r.destination, prev, s.attraction_id)
                # V-08 legs and stop arithmetic
                if leg.from_ != prev or leg.to not in (None, s.attraction_id) or leg.mode != self.lt_mode:
                    self.err("V-08", f"{tag} leg to {s.attraction_id} starts at {leg.from_}, expected {prev}")
                if abs(leg.minutes - mins) > 1 or abs(leg.km - km) > 0.05:
                    self.err("V-08", f"{tag} leg to {s.attraction_id} {leg.minutes} min {leg.km} km, matrix {mins} min {km} km")
                depart = prev_end if prev_end is not None else arrive - leg.minutes
                if arrive != depart + leg.minutes or start < arrive or end != start + at.visit:
                    self.err("V-08", f"{tag} {s.attraction_id} times {s.arrive}/{s.start}/{s.end} are inconsistent")
                # V-03 per-stop costs
                if leg.cost != self.ride(leg.km) or s.entry_cost != self.P * at.fee:
                    self.err("V-03", f"{tag} {s.attraction_id} leg or entry cost does not match the tariff")
                # V-06, V-07 opening
                if d.weekday in at.closed:
                    self.err("V-06", f"{tag} visits {s.attraction_id} on a closed weekday")
                if start < at.open or end > at.close or (at.fixed_slot and start != at.open):
                    self.err("V-07", f"{tag} {s.attraction_id} {s.start}-{s.end} outside {at.open // 60:02d}:{at.open % 60:02d}-"
                                     f"{at.close // 60:02d}:{at.close % 60:02d}")
                busy += [(depart, arrive), (start, end)]
                entry_total += s.entry_cost
                local_total += leg.cost
                prev, prev_end = s.attraction_id, end
            first_dep = last_ret = None
            if d.stops:
                first_dep = _t(d.stops[0].arrive) - d.stops[0].leg_from_prev.minutes
                rl = d.return_leg
                if rl is None:
                    self.err("V-08", f"{tag} has no return leg")
                else:
                    km, mins = ds.travel(r.destination, prev, hotel)
                    if rl.from_ != prev or rl.to != hotel or rl.mode != self.lt_mode or abs(rl.minutes - mins) > 1 \
                            or abs(rl.km - km) > 0.05:
                        self.err("V-08", f"{tag} return leg {rl.from_}->{rl.to} {rl.minutes} min, matrix {mins} min")
                    if rl.cost != self.ride(rl.km):
                        self.err("V-03", f"{tag} return leg cost does not match the tariff")
                    last_ret = prev_end + rl.minutes
                    busy.append((prev_end, last_ret))
                    local_total += rl.cost
                if first_dep < w["start"] or (last_ret is not None and last_ret > w["end"]):
                    self.err("V-09", f"{tag} runs {first_dep}-{last_ret}, window {w['start']}-{w['end']}")
            elif d.return_leg is not None:
                self.err("V-08", f"{tag} has a return leg but no stops")
            # V-10 span and count
            lunch_iv = None
            if d.lunch is not None:
                lunch_iv = (_t(d.lunch[0]), _t(d.lunch[1]))
            if d.stops and last_ret is not None:
                span = last_ret - first_dep
                if lunch_iv and first_dep <= lunch_iv[0] and lunch_iv[1] <= last_ret:
                    span -= lunch_iv[1] - lunch_iv[0]
                if span > w["usable"]:
                    self.err("V-10", f"{tag} span {span} min > usable {w['usable']}")
            if len(d.stops) > w["max"]:
                self.err("V-10", f"{tag} has {len(d.stops)} activities > {w['max']}")
            # V-11 lunch details
            if lunch_iv is not None and w["lunch"]:
                lc = c["lunch"]
                ls, le = lunch_iv
                if le - ls != lc["minutes"] or not _t(lc["earliest"]) <= ls <= _t(lc["latest"]) \
                        or ls < w["start"] or le > w["end"]:
                    self.err("V-11", f"{tag} lunch {d.lunch} breaks the lunch rule")
                elif any(ls < b and a < le for a, b in busy):
                    self.err("V-11", f"{tag} lunch {d.lunch} overlaps a visit or a leg")

        # V-03 budget lines
        b = p.budget
        food = round_half_up(self.P * self.D * ds.food[tier] * ds.cities[r.destination].food_multiplier)
        stay = (self.D - 1) * rooms * h.price
        usable = math.floor(r.budget_total * c["usable_budget_share"])
        exp = {"outbound": oc, "return_": rc, "stay": stay, "food": food, "entry_fees": entry_total,
               "local_travel": local_total}
        for k, v in exp.items():
            if getattr(b, k) != v:
                self.err("V-03", f"budget {k.rstrip('_')} {getattr(b, k)}, recomputed {v}")
        if ob.cost != oc or rt.cost != rc or p.hotel.cost != stay:
            self.err("V-03", "transport or hotel cost does not match its budget line")
        if b.total != sum(exp.values()):
            self.err("V-03", f"total {b.total} is not the sum of the lines {sum(exp.values())}")
        if (b.budget_total, b.usable_budget, b.contingency) != (r.budget_total, usable, r.budget_total - usable):
            self.err("V-03", "budget_total, usable_budget or contingency is wrong")
        # V-04 budget rule
        if sum(exp.values()) > usable:
            self.err("V-04", f"total {sum(exp.values())} > usable budget {usable}")
        return self.fail


def validate(plan: Plan, request: TripRequest, dataset: Dataset, config: dict | None = None) -> list[str]:
    cfg = config if config is not None else yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return _Check(plan, request, dataset, cfg).run()
