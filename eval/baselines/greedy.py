"""Greedy baseline (008 EVAL-FR-01).

Cheapest available transport each way, cheapest hotel in the user's tier, then activities in descending
v(a) ÷ (fee × P + 1) order (locks first), each put on the first day where it still fits when appended to that
day's visit order (no routing optimisation), while the exact cost stays within the usable budget. Same data,
time model, cost model and value function as Tripwise (it reuses the engine's building blocks), so the
validator judges it the same way.
"""

from __future__ import annotations

import time

from tripwise import config as config_mod, data as data_mod
from tripwise.engine import Context, build, hotels_for, lines, setup
from tripwise.models import Infeasible, TripRequest
from tripwise.stage2 import Routed, schedule_day
from tripwise.timemodel import day_windows


def plan(req: TripRequest, ds=None, cfg=None):
    cfg = cfg or config_mod.default()
    ds = ds or data_mod.load_cached(str(cfg.data_dir))
    t0 = time.perf_counter()
    ctx = setup(req, ds, cfg)
    if not isinstance(ctx, Context):
        return ctx
    oi = min(range(len(ctx.outs)), key=lambda i: (ctx.cand.out_cost[i], i))
    ri = min(range(len(ctx.rets)), key=lambda i: (ctx.cand.ret_cost[i], i))
    hotel = min(hotels_for(ds, req, [req.prefs.comfort]), key=lambda h: (h.price, h.hotel_id))
    wins = day_windows(req, cfg, ctx.outs[oi], ctx.rets[ri])
    city, P = req.destination, req.people
    orders = [[] for _ in wins]

    def routed() -> Routed:
        return Routed([schedule_day(ds, cfg, city, hotel, w, o) for w, o in zip(wins, orders)], [])

    if lines(ctx, hotel, oi, ri, routed())["total"] > ctx.usable:
        return Infeasible(reason="budget", min_budget_total=None,
                          message="Greedy: transport, hotel and food alone exceed the usable budget.")
    locks = set(req.fixed_ids())
    pool = sorted(ctx.filt.kept, key=lambda a: (a.attraction_id not in locks,
                                                -ctx.v_all[a.attraction_id] / (a.fee * P + 1), a.attraction_id))
    for a in pool:
        for i, w in enumerate(wins):
            if not w.active or w.weekday in a.closed or (a.attraction_id in req.pins and req.pins[a.attraction_id] != w.day):
                continue
            if schedule_day(ds, cfg, city, hotel, w, orders[i] + [a]) is None:
                continue
            orders[i].append(a)
            if lines(ctx, hotel, oi, ri, routed())["total"] <= ctx.usable:
                break
            orders[i].pop()                      # fits in time but not in money
    r = routed()
    return build(ctx, hotel, oi, ri, r, lines(ctx, hotel, oi, ri, r), 1, 0, 0, None, wins, t0)
