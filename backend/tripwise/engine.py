"""The planning pipeline (002 Spec §7–8, addendum A5; ENG-FR-04, ENG-FR-06, ENG-FR-07).

plan(request) -> Plan | Infeasible | InternalError
  pre-filter → hotel loop (stage 1) → stage 2 → feedback cuts → exact costing and budget repair →
  validator gate. Variants (variants.py) call run() with other objectives and hotel tiers.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from fractions import Fraction

from tripwise import config as config_mod
from tripwise import costs, data as data_mod, stage1, stage2, value
from tripwise.config import Config, fmt
from tripwise.data import TIERS, Dataset, Hotel
from tripwise.models import (Budget, Day, HotelOut, Infeasible, InternalError, Leg, NearMiss, Outbound, Plan,
                             Return, SolverInfo, Stop, Transport, TripRequest)
from tripwise.prefilter import Filtered, fits, prefilter
from tripwise.timemodel import day_windows, door_minutes, options, outbound_times, return_times
from validator.validate import validate


def inr(n: int) -> str:
    """₹ with Indian digit grouping: 152500 -> ₹1,52,500."""
    s = str(n)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return "₹" + s


@dataclass
class Context:
    ds: Dataset
    cfg: Config
    req: TripRequest
    outs: list
    rets: list
    filt: Filtered
    cand: stage1.Candidate
    usable: int
    v_all: dict = field(default_factory=dict)        # v(a) for every attraction of the city


def hotels_for(ds: Dataset, req: TripRequest, tiers: list) -> list[Hotel]:
    return [h for t in tiers for h in ds.hotels_by.get((req.destination, t), [])]


def tiers_for(req: TripRequest, offset: int = 0) -> list[str]:
    i = TIERS.index(req.prefs.comfort)
    out = [TIERS[i]]
    j = i + offset
    if offset and 0 <= j < len(TIERS):
        out.append(TIERS[j])
    return out


def setup(req: TripRequest, ds: Dataset, cfg: Config) -> Context | Infeasible:
    outs, rets = options(ds, cfg, req, "out"), options(ds, cfg, req, "ret")
    if not outs or not rets:
        missing = "outbound" if not outs else "return"
        return Infeasible(reason="no_route", message=f"No usable {missing} transport between {req.origin} and "
                                                     f"{req.destination} with the chosen modes.")
    filt = prefilter(ds, cfg, req, outs, rets)
    if filt.lock_problem:
        a = ds.attractions.get(filt.lock_problem)
        name = a.name if a else filt.lock_problem
        return Infeasible(reason="lock_impossible", attraction_id=filt.lock_problem,
                          message=f"{name} cannot be scheduled on any day of this trip.")
    cand = stage1.prepare(ds, cfg, req, outs, rets, filt.kept)
    v_all = {a.attraction_id: value.activity(a, req.prefs, cfg) for a in ds.by_city[req.destination]}
    return Context(ds, cfg, req, outs, rets, filt, cand, costs.usable_budget(req.budget_total, cfg), v_all)


# --- exact costing -------------------------------------------------------------------------------------

def leg_costs(ctx: Context, routed: stage2.Routed) -> dict:
    """attraction_id -> (leg-in cost, return-leg cost or 0)."""
    out = {}
    for d in routed.days:
        for i, s in enumerate(d.stops):
            back = costs.ride(ctx.ds, ctx.cfg, ctx.req, d.return_km) if i == len(d.stops) - 1 else 0
            out[s.attraction.attraction_id] = (costs.ride(ctx.ds, ctx.cfg, ctx.req, s.leg_km), back)
    return out


def lines(ctx: Context, hotel: Hotel, oi: int, ri: int, routed: stage2.Routed) -> dict:
    lc = leg_costs(ctx, routed)
    entry = sum(costs.entry(ctx.req, s.attraction.fee) for d in routed.days for s in d.stops)
    b = {"outbound": ctx.cand.out_cost[oi], "return": ctx.cand.ret_cost[ri], "stay": costs.stay(ctx.req, hotel),
         "food": ctx.cand.food, "entry_fees": entry, "local_travel": sum(a + b for a, b in lc.values())}
    b["total"] = sum(b.values())
    return b


def plan_value(ctx: Context, hotel: Hotel, oi: int, ri: int, routed: stage2.Routed) -> float:
    stops = [s for d in routed.days for s in d.stops]
    minutes = sum(s.leg_minutes for s in stops) + sum(d.return_minutes for d in routed.days if d.stops)
    o, r = ctx.outs[oi], ctx.rets[ri]
    return value.plan(sum(ctx.v_all[s.attraction.attraction_id] for s in stops), o.comfort, r.comfort,
                      int(o.preferred) + int(r.preferred), minutes, hotel.tier, ctx.cfg)


# --- minimum budget (§8.2) -----------------------------------------------------------------------------

@dataclass
class Cheapest:
    cost: int
    oi: int
    ri: int
    hotel: Hotel
    chosen: list


def cheapest(ctx: Context, hotels: list) -> Cheapest | None:
    """The cheapest exactly costed plan with ≥ 1 activity and all locks."""
    ds, cfg, req = ctx.ds, ctx.cfg, ctx.req
    locks = [ds.attractions[a] for a in req.locks]
    best: Cheapest | None = None
    combos = sorted(((ctx.cand.out_cost[i] + ctx.cand.ret_cost[j], i, j)
                     for i in range(len(ctx.outs)) for j in range(len(ctx.rets))))
    for tcost, oi, ri in combos:
        base0 = tcost + ctx.cand.food
        if best and base0 >= best.cost:
            break
        wins = day_windows(req, cfg, ctx.outs[oi], ctx.rets[ri])
        for h in hotels:
            base = base0 + costs.stay(req, h)
            if best and base >= best.cost:
                continue
            if locks:
                routed = stage2.route(ds, cfg, req, h, wins, locks, ctx.v_all)
                if routed.dropped:
                    continue
                c = lines(ctx, h, oi, ri, routed)["total"]
                if best is None or c < best.cost:
                    best = Cheapest(c, oi, ri, h, locks)
                continue
            ranked = []
            for a in ctx.filt.kept:
                km_in = ds.travel(req.destination, h.hotel_id, a.attraction_id)[0]
                km_out = ds.travel(req.destination, a.attraction_id, h.hotel_id)[0]
                extra = costs.entry(req, a.fee) + costs.ride(ds, cfg, req, km_in) + costs.ride(ds, cfg, req, km_out)
                ranked.append((extra, a.attraction_id, a))
            ranked.sort(key=lambda t: (t[0], t[1]))
            for extra, _, a in ranked:
                if best and base + extra >= best.cost:
                    break
                if any(fits(a, w) and stage2.schedule_day(ds, cfg, req.destination, h, w, [a]) for w in wins):
                    best = Cheapest(base + extra, oi, ri, h, [a])
                    break
    return best


def min_budget_total(cost: int, cfg: Config) -> int:
    """⌈(cost ÷ usable share) ÷ step⌉ × step, in exact arithmetic."""
    share = Fraction(str(cfg.usable_budget_share))
    step = cfg.min_budget_round
    return math.ceil(Fraction(cost) / share / step) * step


def infeasible_budget(ctx: Context, hotels: list) -> Infeasible:
    req = ctx.req
    ch = cheapest(ctx, hotels)
    if ch is None:
        return Infeasible(reason="budget", message=f"No activity can be scheduled on this {req.days}-day trip.")
    mb = min_budget_total(ch.cost, ctx.cfg)
    who = f"{req.people} {'person' if req.people == 1 else 'people'}"
    if req.locks:
        free = TripRequest.model_validate(req.model_dump() | {"locks": []})
        fctx = setup(free, ctx.ds, ctx.cfg)
        fch = cheapest(fctx, hotels) if isinstance(fctx, Context) else None
        if fch is not None and fch.cost <= ctx.usable:
            return Infeasible(reason="lock_over_budget", min_budget_total=mb,
                              message=f"The locked activities alone do not fit {inr(req.budget_total)}. "
                                      f"With them, the cheapest plan needs about {inr(mb)}.")
    return Infeasible(reason="budget", min_budget_total=mb,
                      message=f"No plan fits {inr(req.budget_total)} for {who} over {req.days} days. "
                              f"The cheapest workable plan needs about {inr(mb)}.")


# --- the pipeline --------------------------------------------------------------------------------------

@dataclass
class Outcome:
    result: object               # Plan | Infeasible | InternalError
    chosen: list = field(default_factory=list)


def run(ctx: Context, mode: str = "max_value", hotels: list | None = None, vstar: float | None = None,
        variant: str | None = None, t0: float | None = None) -> Outcome:
    ds, cfg, req = ctx.ds, ctx.cfg, ctx.req
    t0 = t0 if t0 is not None else time.perf_counter()
    hotels = hotels if hotels is not None else hotels_for(ds, req, tiers_for(req))
    sel = stage1.best(ds, cfg, ctx.cand, hotels, mode, budget=ctx.usable, vstar=vstar, min_activities=1)
    if sel is None:
        return Outcome(infeasible_budget(ctx, hotels))
    hotel, oi, ri = sel.hotel, sel.out, sel.ret
    wins = day_windows(req, cfg, ctx.outs[oi], ctx.rets[ri])
    chosen = sel.chosen
    cuts: set = set()
    iters = 0
    routed = stage2.route(ds, cfg, req, hotel, wins, chosen, ctx.v_all)
    while routed.dropped and iters < cfg.max_feedback_iters:
        cuts |= {a.attraction_id for a in routed.dropped}
        nxt = stage1.solve(ds, cfg, ctx.cand, hotel, mode, budget=ctx.usable, vstar=vstar,
                           cuts=frozenset(cuts), fix=(oi, ri))
        iters += 1
        if nxt is None:
            break
        chosen = nxt.chosen
        routed = stage2.route(ds, cfg, req, hotel, wins, chosen, ctx.v_all)
    placed = [s.attraction for d in routed.days for s in d.stops]
    if any(lid not in {a.attraction_id for a in placed} for lid in req.locks):
        lid = next(l for l in req.locks if l not in {a.attraction_id for a in placed})
        return Outcome(Infeasible(reason="lock_impossible", attraction_id=lid,
                                  message=f"{ds.attractions[lid].name} cannot be fitted into this trip's days."))
    repairs = 0
    b = lines(ctx, hotel, oi, ri, routed)
    while b["total"] > ctx.usable and placed:
        lc = leg_costs(ctx, routed)
        removable = [a for a in placed if a.attraction_id not in req.locks]
        if not removable or repairs >= cfg.max_repairs:
            break
        worst = min(removable, key=lambda a: (ctx.v_all[a.attraction_id]
                                              / max(1, costs.entry(req, a.fee) + sum(lc[a.attraction_id])),
                                              a.attraction_id))
        keep = [a for a in placed if a is not worst]
        routed = stage2.route(ds, cfg, req, hotel, wins, keep, ctx.v_all)
        placed = [s.attraction for d in routed.days for s in d.stops]
        b = lines(ctx, hotel, oi, ri, routed)
        repairs += 1
    if b["total"] > ctx.usable or not placed:
        ch = cheapest(ctx, hotels)
        if ch is None or ch.cost > ctx.usable:
            return Outcome(infeasible_budget(ctx, hotels))
        hotel, oi, ri = ch.hotel, ch.oi, ch.ri
        wins = day_windows(req, cfg, ctx.outs[oi], ctx.rets[ri])
        routed = stage2.route(ds, cfg, req, hotel, wins, ch.chosen, ctx.v_all)
        placed = [s.attraction for d in routed.days for s in d.stops]
        b = lines(ctx, hotel, oi, ri, routed)
    p = build(ctx, hotel, oi, ri, routed, b, len(hotels), iters, repairs, variant, wins, t0)
    fails = validate(p, req, ds, cfg.as_dict())
    if fails:
        return Outcome(InternalError(failures=fails), placed)
    return Outcome(p, placed)


def near_misses(ctx: Context, chosen_ids: set, total: int, hotel: Hotel, wins: list) -> list[NearMiss]:
    ds, req, cfg = ctx.ds, ctx.req, ctx.cfg
    pool = [a for a in ds.by_city[req.destination] if a.attraction_id not in chosen_ids
            and ctx.filt.removed.get(a.attraction_id) != "excluded"]
    pool.sort(key=lambda a: (-ctx.v_all[a.attraction_id], a.attraction_id))
    out = []
    for a in pool[:cfg.near_miss_count]:
        if ctx.filt.removed.get(a.attraction_id) == "closed" or not any(fits(a, w) for w in wins):
            reason = "closed"
        else:
            km = ds.travel(req.destination, hotel.hotel_id, a.attraction_id)[0]
            extra = costs.entry(req, a.fee) + costs.est_local(ds, cfg, req, km)
            reason = "budget" if total + extra > ctx.usable else "time"
        out.append(NearMiss(attraction_id=a.attraction_id, name=a.name, reason=reason))
    return out


def build(ctx: Context, hotel: Hotel, oi: int, ri: int, routed: stage2.Routed, b: dict, n_hotels: int,
          iters: int, repairs: int, variant: str | None, wins: list, t0: float) -> Plan:
    ds, cfg, req = ctx.ds, ctx.cfg, ctx.req
    o, r = ctx.outs[oi], ctx.rets[ri]
    ot, rt = outbound_times(o, cfg), return_times(r, cfg)
    mode = costs.local_mode(req, cfg)
    days = []
    for d in routed.days:
        stops, prev = [], hotel.hotel_id
        for s in d.stops:
            aid = s.attraction.attraction_id
            stops.append(Stop(attraction_id=aid, name=s.attraction.name, arrive=fmt(s.arrive), start=fmt(s.start),
                              end=fmt(s.end), entry_cost=costs.entry(req, s.attraction.fee),
                              leg_from_prev=Leg(**{"from": prev}, to=aid, minutes=s.leg_minutes, km=s.leg_km, mode=mode,
                                                cost=costs.ride(ds, cfg, req, s.leg_km))))
            prev = aid
        ret_leg = Leg(**{"from": prev}, to=hotel.hotel_id, minutes=d.return_minutes, km=d.return_km, mode=mode,
                      cost=costs.ride(ds, cfg, req, d.return_km)) if d.stops else None
        w = d.window
        days.append(Day(day=w.day, date=w.date, weekday=w.weekday,
                        window=[fmt(w.start), fmt(w.end)] if w.active else None,
                        lunch=[fmt(d.lunch[0]), fmt(d.lunch[1])] if d.lunch else None,
                        stops=stops, return_leg=ret_leg))
    chosen_ids = {s.attraction.attraction_id for d in routed.days for s in d.stops}
    budget = Budget(outbound=b["outbound"], **{"return": b["return"]}, stay=b["stay"], food=b["food"],
                    entry_fees=b["entry_fees"], local_travel=b["local_travel"], total=b["total"],
                    usable_budget=ctx.usable, contingency=costs.contingency(req.budget_total, cfg),
                    budget_total=req.budget_total, estimate_label=ds.estimate_label())
    return Plan(variant=variant, dataset_version=ds.label, request_hash=req.request_hash(),
                value=round(plan_value(ctx, hotel, oi, ri, routed), 2),
                transport=Transport(outbound=Outbound(mode=o.mode, **{"class": o.cls}, depart=fmt(ot["depart"]),
                                                      arrive_centre=fmt(ot["arrive_centre"]), minutes=door_minutes(o, cfg),
                                                      overnight=o.overnight, cost=b["outbound"]),
                                    **{"return": Return(mode=r.mode, **{"class": r.cls}, leave_centre=fmt(rt["leave_centre"]),
                                                        arrive_origin=fmt(rt["arrive_origin"]),
                                                        minutes=door_minutes(r, cfg), overnight=r.overnight,
                                                        cost=b["return"])}),
                hotel=HotelOut(hotel_id=hotel.hotel_id, name=hotel.name, tier=hotel.tier, nights=req.days - 1,
                               rooms=costs.rooms(req.people), price_per_room_night=hotel.price, cost=b["stay"]),
                days=days, budget=budget, near_misses=near_misses(ctx, chosen_ids, b["total"], hotel, wins),
                solver=SolverInfo(hotel_candidates=n_hotels, feedback_iters=iters, repairs=repairs,
                                  solve_ms=round((time.perf_counter() - t0) * 1000)))


def plan(req: TripRequest, ds: Dataset | None = None, cfg: Config | None = None):
    """Single plan in the user's tier: maximise value within the usable budget."""
    t0 = time.perf_counter()
    cfg = cfg or config_mod.default()
    ds = ds or data_mod.load_cached(str(cfg.data_dir))
    ctx = setup(req, ds, cfg)
    if not isinstance(ctx, Context):
        return ctx
    return run(ctx, "max_value", t0=t0).result
