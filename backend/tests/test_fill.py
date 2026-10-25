"""Fill step (ENG-FR-13): after exact routing the engine adds unchosen candidates that still fit a day and the budget,
per variant objective, and the result still passes the validator."""

import json
from pathlib import Path

from tripwise import config, data, engine
from tripwise.engine import Context, hotels_for, setup, tiers_for
from tripwise.models import Plan, TripRequest
from validator.validate import validate

TRIPS = {t["id"]: t for t in json.loads((Path(__file__).resolve().parents[2] / "eval" / "test_trips.json").read_text(encoding="utf-8"))}


def without_fill(monkeypatch, req):
    monkeypatch.setattr(engine, "fill", lambda ctx, h, oi, ri, w, r, b, m, v: (r, b))
    return engine.plan(req)


def test_fill_adds_value_and_stays_valid(monkeypatch):
    ds, cfg = data.default(), config.default()
    req = TripRequest.model_validate(TRIPS["T06"]["request"])       # left room after routing before the fill step
    filled = engine.plan(req)
    assert isinstance(filled, Plan) and validate(filled, req, ds, cfg.as_dict()) == []
    plain = without_fill(monkeypatch, req)
    n = lambda p: sum(len(d.stops) for d in p.days)   # noqa: E731
    assert filled.value > plain.value and n(filled) > n(plain)
    assert filled.budget.total <= filled.budget.usable_budget


def test_saver_does_not_fill_and_balanced_pays_for_cost():
    ds, cfg = data.default(), config.default()
    req = TripRequest.model_validate(TRIPS["T06"]["request"])
    ctx = setup(req, ds, cfg)
    assert isinstance(ctx, Context)
    out = engine.run(ctx, "max_value", hotels_for(ds, req, tiers_for(req)))
    exp = out.result
    hotel = ds.hotels[exp.hotel.hotel_id]
    # rebuild a routed plan with one stop removed, then check each objective's fill decision on it
    from tripwise.stage2 import Routed, schedule_day
    from tripwise.timemodel import day_windows
    oi = next(i for i, o in enumerate(ctx.outs) if (o.mode, o.cls) == (exp.transport.outbound.mode, exp.transport.outbound.class_)
              and engine.outbound_times(o, cfg)["depart"] == int(exp.transport.outbound.depart[:2]) * 60 + int(exp.transport.outbound.depart[3:]))
    ri = next(i for i, r in enumerate(ctx.rets) if (r.mode, r.cls) == (exp.transport.return_.mode, exp.transport.return_.class_)
              and engine.return_times(r, cfg)["leave_centre"] == int(exp.transport.return_.leave_centre[:2]) * 60 + int(exp.transport.return_.leave_centre[3:]))
    wins = day_windows(req, cfg, ctx.outs[oi], ctx.rets[ri])
    orders = [[ds.attractions[s.attraction_id] for s in d.stops] for d in exp.days]
    last = next(i for i in range(len(orders) - 1, -1, -1) if orders[i])
    orders[last] = orders[last][:-1]
    routed = Routed([schedule_day(ds, cfg, req.destination, hotel, w, o) for w, o in zip(wins, orders)], [])
    b = engine.lines(ctx, hotel, oi, ri, routed)
    r_saver, b_saver = engine.fill(ctx, hotel, oi, ri, wins, routed, b, "min_cost", exp.value)
    assert r_saver is routed and b_saver is b                         # Saver never fills
    r_exp, b_exp = engine.fill(ctx, hotel, oi, ri, wins, routed, b, "max_value", None)
    assert sum(len(d.stops) for d in r_exp.days) > sum(len(d.stops) for d in routed.days)
    assert b_exp["total"] <= ctx.usable
    # Balanced with a huge V* treats every rupee as expensive: nothing is added
    r_bal, _ = engine.fill(ctx, hotel, oi, ri, wins, routed, b, "balanced", 1e9)
    assert sum(len(d.stops) for d in r_bal.days) == sum(len(d.stops) for d in routed.days)
