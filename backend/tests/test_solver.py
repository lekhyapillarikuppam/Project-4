"""T09–T11: pre-filter, stage 1 limits and stage 2 routing on three trips."""

import pytest

from tripwise import config, data, engine, stage1
from tripwise.models import Infeasible, Plan, TripRequest
from tripwise.prefilter import prefilter
from tripwise.stage1 import est_travel
from tripwise.timemodel import options
from validator.validate import validate

INTERESTS = {"nature": 2, "adventure": 1, "food": 3, "history": 5, "culture": 4, "spiritual": 2, "shopping": 1,
             "relaxation": 2, "nightlife": 0}


def req(origin, dest, start, end, people, budget, pace="balanced", comfort="mid", **kw):
    return TripRequest.model_validate({"origin": origin, "destination": dest, "start_date": start, "end_date": end,
                                       "people": people, "budget_total": budget,
                                       "prefs": {"daily_hours_out": 9, "pace": pace, "comfort": comfort,
                                                 "interests": INTERESTS, "modes": {}, "avoid_crowds": False},
                                       **kw})


TRIPS = [
    req("DEL", "AGR", "2026-12-14", "2026-12-16", 2, 40000, "relaxed", "budget"),     # includes a Monday
    req("BOM", "GOA", "2027-01-08", "2027-01-12", 3, 90000, "packed", "mid"),
    req("CCU", "DJL", "2027-02-01", "2027-02-04", 1, 60000, "balanced", "premium"),
]


def test_prefilter_lock_impossible():
    ds, cfg = data.default(), config.default()
    # GOA-A-30 Arpora market opens on Saturdays only; a Monday-Tuesday trip cannot visit it
    r = req("BOM", "GOA", "2026-12-14", "2026-12-15", 2, 80000, locks=["GOA-A-30"])
    f = prefilter(ds, cfg, r, options(ds, cfg, r, "out"), options(ds, cfg, r, "ret"))
    assert f.removed["GOA-A-30"] == "closed" and f.lock_problem == "GOA-A-30"
    out = engine.plan(r)
    assert isinstance(out, Infeasible) and out.reason == "lock_impossible"
    r2 = req("BOM", "GOA", "2026-12-14", "2026-12-15", 2, 80000, excludes=["GOA-A-01"])
    f2 = prefilter(ds, cfg, r2, options(ds, cfg, r2, "out"), options(ds, cfg, r2, "ret"))
    assert f2.removed["GOA-A-01"] == "excluded"


@pytest.mark.parametrize("r", TRIPS, ids=["DEL-AGR", "BOM-GOA", "CCU-DJL"])
def test_stage1_respects_budget_time_count(r):
    ds, cfg = data.default(), config.default()
    ctx = engine.setup(r, ds, cfg)
    hotels = engine.hotels_for(ds, r, [r.prefs.comfort])
    sel = stage1.best(ds, cfg, ctx.cand, hotels, "max_value", budget=ctx.usable, min_activities=1)
    assert sel is not None
    c = ctx.cand
    assert sel.est_cost <= ctx.usable
    used = sum(a.visit + est_travel(ds, cfg, r.destination, sel.hotel, a) for a in sel.chosen)
    assert used <= c.u_mid + c.u1[sel.out] + c.ud[sel.ret]
    assert len(sel.chosen) <= c.c_mid + c.c1[sel.out] + c.cd[sel.ret]


@pytest.mark.parametrize("r", TRIPS, ids=["DEL-AGR", "BOM-GOA", "CCU-DJL"])
def test_routed_plan_passes_validator(r):
    p = engine.plan(r)
    assert isinstance(p, Plan), p
    assert validate(p, r, data.default(), config.default().as_dict()) == []
    assert p.activity_ids()
