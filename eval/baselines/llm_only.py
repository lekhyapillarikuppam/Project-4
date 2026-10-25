"""LLM-only baseline (008 EVAL-FR-01, amended 2026-10-26).

One Groq call per trip, same model as the app. The prompt is a compact table (no prose beyond the rules): the
request, each day's window, the top 25 attractions by value v(a) (id, name, open–close, closed days, fee, visit
minutes, tags), the transport options with group prices and the hotels in the user's tier. Kept under about
6,000 tokens so one request fits Groq's free-tier per-minute limit.

The model returns its choices (transport options, hotel, each day's ordered activities). Those are rebuilt into a
Plan with the same time model, cost model and value function as Tripwise: a day whose order fits is timed by the
engine's scheduler; a day that does not fit is timed naively (stops back to back from the window start, no
lunch), so the validator reports what the model got wrong. Output that cannot be parsed, or names unknown
transport options, hotels or attractions, is a failed plan.
"""

from __future__ import annotations

import json
import time

from api.ai import groq_client
from tripwise import config as config_mod, costs, data as data_mod
from tripwise.config import fmt
from tripwise.engine import Context, build, hotels_for, lines, setup
from tripwise.models import TripRequest
from tripwise.stage2 import DaySchedule, Routed, StopTime, schedule_day
from tripwise.timemodel import day_windows, door_minutes, outbound_times, return_times

TOP_N = 25
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Failed(Exception):
    """The model's answer could not be turned into a plan."""


def _t(m: int) -> str:
    return fmt(m)


def prompt(ctx: Context) -> tuple[str, list]:
    ds, cfg, req = ctx.ds, ctx.cfg, ctx.req
    top = sorted(ctx.filt.kept, key=lambda a: (-ctx.v_all[a.attraction_id], a.attraction_id))[:TOP_N]
    pace = cfg.pace[req.prefs.pace]
    hotels = hotels_for(ds, req, [req.prefs.comfort])
    rows = ["id|name|open-close|closed|fee_pp|visit_min|tags"]
    rows += [f"{a.attraction_id}|{a.name}|{_t(a.open)}-{_t(a.close)}|{','.join(WEEKDAYS[d] for d in sorted(a.closed)) or '-'}"
             f"|{a.fee}|{a.visit}|{','.join(a.tags)}" for a in top]
    outs = ["opt|mode|class|depart|arrive_city_centre|door_min|cost_group"]
    for i, o in enumerate(ctx.outs):
        t = outbound_times(o, cfg)
        outs.append(f"{i}|{o.mode}|{o.cls}|{_t(t['depart'])}|{_t(t['arrive_centre'])}|{door_minutes(o, cfg)}|{ctx.cand.out_cost[i]}")
    rets = ["opt|mode|class|leave_city_centre|arrive_home|door_min|cost_group"]
    for i, r in enumerate(ctx.rets):
        t = return_times(r, cfg)
        rets.append(f"{i}|{r.mode}|{r.cls}|{_t(t['leave_centre'])}|{_t(t['arrive_origin'])}|{door_minutes(r, cfg)}|{ctx.cand.ret_cost[i]}")
    hrows = ["id|name|price_per_room_night"] + [f"{h.hotel_id}|{h.name}|{h.price}" for h in hotels]
    nights, rooms = req.days - 1, -(-req.people // 2)
    lc = cfg.lunch
    lt = ds.local[(req.destination, costs.local_mode(req, cfg))]
    vehicles = costs.vehicles(req.people, lt.capacity)
    text = f"""Plan a trip. Reply with one JSON object only:
{{"outbound": <opt>, "return": <opt>, "hotel_id": "<id>", "days": [{{"day": 1, "stops": ["<attraction id>", ...]}}, ...]}}
Goal: the most value for the traveller's interests within the budget; every stop must fit its day.
Trip: {ds.cities[req.origin].name} to {ds.cities[req.destination].name}, {req.start_date} to {req.end_date} ({req.days} days),
{req.people} people, usable budget Rs {ctx.usable} for everything.
Interests 0-5: {json.dumps(req.prefs.interests)}; pace {req.prefs.pace}: at most {pace['max']} stops a day.
Day windows when outbound opt 0 / return opt 0 are used (day 1 starts after arrival, the last day ends before departure):
{"; ".join(f"day {w.day} {WEEKDAYS[w.weekday]} {_t(w.start)}-{_t(w.end)}" for w in day_windows(req, cfg, ctx.outs[0], ctx.rets[0]))}
Rules: a stop needs open <= start and start + visit_min <= close, and not a closed weekday; lunch {lc['minutes']} min
starting {lc['earliest']}-{lc['latest']} on full days; local travel between places takes 10-40 min; each ride costs
(Rs {lt.min_fare} + Rs {lt.per_km}/km beyond {lt.min_km} km) x {vehicles} vehicle(s). Costs: outbound + return (group prices below) + hotel
({nights} nights x {rooms} rooms x price) + food Rs {ctx.cand.food} + entry fees (fee_pp x {req.people}) + local travel.
Attractions:
{chr(10).join(rows)}
Outbound options:
{chr(10).join(outs)}
Return options:
{chr(10).join(rets)}
Hotels:
{chr(10).join(hrows)}"""
    return text, top


def realise(ctx: Context, obj: dict, t0: float):
    ds, cfg, req = ctx.ds, ctx.cfg, ctx.req
    try:
        oi, ri = int(obj["outbound"]), int(obj["return"])
        hotel = ds.hotels[obj["hotel_id"]]
        days_in = {int(d["day"]): list(d.get("stops") or []) for d in obj["days"]}
    except (KeyError, TypeError, ValueError) as exc:
        raise Failed(f"bad shape: {exc}") from None
    if not (0 <= oi < len(ctx.outs) and 0 <= ri < len(ctx.rets)):
        raise Failed("unknown transport option")
    wins = day_windows(req, cfg, ctx.outs[oi], ctx.rets[ri])
    sched = []
    for w in wins:
        ids = days_in.get(w.day, [])
        if any(i not in ds.attractions for i in ids):
            raise Failed("unknown attraction id")
        order = [ds.attractions[i] for i in ids]
        s = schedule_day(ds, cfg, req.destination, hotel, w, order)
        sched.append(s if s is not None else naive(ds, req.destination, hotel, w, order))
    r = Routed(sched, [])
    return build(ctx, hotel, oi, ri, r, lines(ctx, hotel, oi, ri, r), 1, 0, 0, None, wins, t0)


def naive(ds, city, hotel, w, order) -> DaySchedule:
    """Back-to-back times from the window start, no lunch: what the model's order means when it does not fit."""
    stops, prev, cur = [], hotel.hotel_id, w.start
    for a in order:
        km, mins = ds.travel(city, prev, a.attraction_id) if a.city_id == city else (0.0, 0)
        arrive = cur + mins
        start = max(arrive, a.open)
        stops.append(StopTime(a, mins, km, arrive, start, start + a.visit))
        cur, prev = start + a.visit, a.attraction_id
    back_km, back_min = ds.travel(city, prev, hotel.hotel_id) if stops and stops[-1].attraction.city_id == city else (0.0, 0)
    return DaySchedule(w, stops, back_min, back_km, None)


def plan(req: TripRequest, ds=None, cfg=None):
    """(Plan | Infeasible | None, info). None means a failed plan; info has the reason, tokens and seconds."""
    cfg = cfg or config_mod.default()
    ds = ds or data_mod.load_cached(str(cfg.data_dir))
    t0 = time.perf_counter()
    ctx = setup(req, ds, cfg)
    if not isinstance(ctx, Context):
        return ctx, {"reason": "infeasible request"}
    text, _ = prompt(ctx)
    info: dict = {"prompt_chars": len(text)}
    try:
        msg = groq_client.chat([{"role": "user", "content": text}], temperature=config_mod.default().groq["temperature_tools"],
                               json_mode=True, max_tokens=3000)
        obj = json.loads(msg.get("content") or "")
        p = realise(ctx, obj, t0)
    except groq_client.Unavailable as exc:
        return None, info | {"reason": f"groq unavailable: {exc}", "seconds": round(time.perf_counter() - t0, 2)}
    except (json.JSONDecodeError, Failed) as exc:
        return None, info | {"reason": f"failed: {exc}", "seconds": round(time.perf_counter() - t0, 2)}
    return p, info | {"choice": obj, "seconds": round(time.perf_counter() - t0, 2)}
