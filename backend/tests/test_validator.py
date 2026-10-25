"""ENG-AT-05: validator self-tests — one hand-broken plan per check V-01…V-13, each caught by exactly that check."""

import copy
import dataclasses

import pytest

from tripwise import config, data, engine
from tripwise.models import Plan, TripRequest
from validator.validate import validate

REQ = {"origin": "BLR", "destination": "JAI", "start_date": "2026-12-18", "end_date": "2026-12-21", "people": 2,
       "budget_total": 90000,
       "prefs": {"daily_hours_out": 9, "pace": "balanced", "comfort": "mid", "avoid_crowds": False,
                 "modes": {"train": "neutral", "bus": "avoid", "flight": "preferred"},
                 "interests": {"nature": 1, "adventure": 0, "food": 4, "history": 5, "culture": 3, "spiritual": 0,
                               "shopping": 2, "relaxation": 1, "nightlife": 0}},
       "locks": [], "excludes": []}


@pytest.fixture(scope="module")
def base():
    ds = data.default()
    req = TripRequest.model_validate(REQ)
    plan = engine.plan(req, ds)
    assert isinstance(plan, Plan)
    return plan, req, ds, config.default().as_dict()


def codes(fails):
    return sorted({f.split(":")[0] for f in fails})


def busy_stop(plan):
    """A day with ≥ 2 stops: (day index, index of a non-first stop)."""
    for i, d in enumerate(plan.days):
        if len(d.stops) >= 2:
            return i, len(d.stops) - 1
    raise AssertionError("plan has no day with two stops")


def with_attraction(ds, aid, **changes):
    ds2 = copy.copy(ds)
    ds2.attractions = dict(ds.attractions)
    ds2.attractions[aid] = dataclasses.replace(ds.attractions[aid], **changes)
    return ds2


def rehash(plan, req):
    p = plan.model_copy(deep=True)
    p.request_hash = req.request_hash()
    return p


def test_valid_plan_passes(base):
    plan, req, ds, cfg = base
    assert validate(plan, req, ds, cfg) == []


def test_v01_request_hash(base):
    plan, req, ds, cfg = base
    p = plan.model_copy(deep=True)
    p.request_hash = "sha256:0"
    assert codes(validate(p, req, ds, cfg)) == ["V-01"]


def test_v02_journey_minutes(base):
    plan, req, ds, cfg = base
    p = plan.model_copy(deep=True)
    p.transport.outbound.minutes += 10
    assert codes(validate(p, req, ds, cfg)) == ["V-02"]


def test_v03_cost_line(base):
    plan, req, ds, cfg = base
    p = plan.model_copy(deep=True)
    p.budget.food += 1
    assert codes(validate(p, req, ds, cfg)) == ["V-03"]


def test_v04_over_budget(base):
    plan, req, ds, cfg = base
    tight = req.model_copy(update={"budget_total": plan.budget.total})      # usable = 90 % of the total
    p = rehash(plan, tight)
    p.budget.budget_total = tight.budget_total
    p.budget.usable_budget = int(tight.budget_total * 0.9)
    p.budget.contingency = tight.budget_total - p.budget.usable_budget
    assert codes(validate(p, tight, ds, cfg)) == ["V-04"]


def test_v05_foreign_attraction(base):
    plan, req, ds, cfg = base
    p = plan.model_copy(deep=True)
    p.days[0].stops[0].attraction_id = "DEL-A-01"
    assert codes(validate(p, req, ds, cfg)) == ["V-05"]


def test_v06_closed_weekday(base):
    plan, req, ds, cfg = base
    day = next(d for d in plan.days if d.stops)
    ds2 = with_attraction(ds, day.stops[0].attraction_id, closed=frozenset({day.weekday}))
    assert codes(validate(plan, req, ds2, cfg)) == ["V-06"]


def test_v07_outside_opening(base):
    plan, req, ds, cfg = base
    di, si = busy_stop(plan)
    s = plan.days[di].stops[si]
    h, m = s.end.split(":")
    ds2 = with_attraction(ds, s.attraction_id, close=int(h) * 60 + int(m) - 1)
    assert codes(validate(plan, req, ds2, cfg)) == ["V-07"]


def test_v08_leg_time(base):
    plan, req, ds, cfg = base
    di, si = busy_stop(plan)
    p = plan.model_copy(deep=True)
    p.days[di].stops[si].leg_from_prev.minutes += 3
    assert codes(validate(p, req, ds, cfg)) == ["V-08"]


def test_v09_window(base):
    plan, req, ds, cfg = base
    p = plan.model_copy(deep=True)
    p.days[1].window = ["08:00", p.days[1].window[1]]
    assert codes(validate(p, req, ds, cfg)) == ["V-09"]


def test_v10_span(base):
    plan, req, ds, cfg = base
    cfg2 = copy.deepcopy(cfg)
    cfg2["pace"]["balanced"]["fill"] = 0.3
    assert codes(validate(plan, req, ds, cfg2)) == ["V-10"]


def test_v11_lunch(base):
    plan, req, ds, cfg = base
    p = plan.model_copy(deep=True)
    d = next(d for d in p.days if d.lunch)
    d.lunch = ["15:00", "16:00"]
    assert codes(validate(p, req, ds, cfg)) == ["V-11"]


def test_v12_excluded_present(base):
    plan, req, ds, cfg = base
    aid = plan.activity_ids()[0]
    req2 = req.model_copy(update={"excludes": [aid]})
    assert codes(validate(rehash(plan, req2), req2, ds, cfg)) == ["V-12"]


def test_v13_hotel_nights(base):
    plan, req, ds, cfg = base
    p = plan.model_copy(deep=True)
    p.hotel.nights += 1
    assert codes(validate(p, req, ds, cfg)) == ["V-13"]
