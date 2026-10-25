"""AI-AT-06: engine extensions pins, day_hours and forced transport (007 Spec §2), checked by V-14–V-16."""

import pytest

from tripwise import config, data, engine
from tripwise.models import Infeasible, Plan, TripRequest
from validator.validate import validate

BASE = {"origin": "DEL", "destination": "JAI", "start_date": "2026-12-14", "end_date": "2026-12-17", "people": 2,
        "budget_total": 60000,
        "prefs": {"daily_hours_out": 9, "pace": "balanced", "comfort": "mid", "avoid_crowds": False, "modes": {},
                  "interests": {"nature": 1, "adventure": 0, "food": 3, "history": 5, "culture": 4, "spiritual": 1,
                                "shopping": 1, "relaxation": 1, "nightlife": 0}},
        "locks": [], "excludes": []}


def plan(**over):
    req = TripRequest.model_validate(BASE | over)
    return req, engine.plan(req)


def valid(req, p):
    assert isinstance(p, Plan), p
    assert validate(p, req, data.default(), config.default().as_dict()) == []
    return p


def day_of(p, aid):
    return next((d.day for d in p.days for s in d.stops if s.attraction_id == aid), None)


def test_pin_moves_an_attraction_to_its_day():
    req, base = plan()
    base = valid(req, base)
    aid, day = next((s.attraction_id, d.day) for d in base.days for s in d.stops)
    target = 3 if day != 3 else 2
    req2, p = plan(pins={aid: target})
    assert day_of(valid(req2, p), aid) == target


def test_impossible_pin():
    # DEL-A-19 National Museum is closed on Mondays; 2026-12-14 (day 1) is a Monday
    assert 0 in data.default().attractions["DEL-A-19"].closed
    req, p = plan(origin="JAI", destination="DEL", pins={"DEL-A-19": 1})
    assert isinstance(p, Infeasible) and p.reason == "pin_impossible" and p.attraction_id == "DEL-A-19"
    req, p = plan(origin="JAI", destination="DEL", pins={"DEL-A-19": 2})
    assert day_of(valid(req, p), "DEL-A-19") == 2
    req, p = plan(pins={"JAI-A-01": 9})
    assert isinstance(p, Infeasible) and p.reason == "pin_impossible"


def test_day_hours_shortens_one_day():
    req, p = plan(day_hours={2: 4})
    p = valid(req, p)
    d2 = p.days[1]
    assert d2.window == ["09:00", "13:00"]
    assert p.days[2].window == ["09:00", "18:00"]


def test_forced_transport():
    req, p = plan(transport={"out": {"mode": "bus", "class": "ACS"}, "ret": {"mode": "train", "class": "SL"}})
    p = valid(req, p)
    assert (p.transport.outbound.mode, p.transport.outbound.class_) == ("bus", "ACS")
    assert (p.transport.return_.mode, p.transport.return_.class_) == ("train", "SL")
    req, p = plan(transport={"out": {"mode": "train", "class": "XX"}})
    assert isinstance(p, Infeasible) and p.reason == "no_route"


@pytest.fixture(scope="module")
def pinned():
    req = TripRequest.model_validate(BASE | {"pins": {}, "day_hours": {3: 6},
                                             "transport": {"out": {"mode": "train", "class": "3A"}}})
    p = engine.plan(req)
    return req, valid(req, p)


def codes(fails):
    return sorted({f.split(":")[0] for f in fails})


def test_v14_v15_v16_catch_broken_plans(pinned):
    req, p = pinned
    ds, cfg = data.default(), config.default().as_dict()
    aid = next(s.attraction_id for d in p.days for s in d.stops if d.day == 2)
    wrong_day = req.model_copy(update={"pins": {aid: 4}})
    q = p.model_copy(deep=True)
    q.request_hash = wrong_day.request_hash()
    assert codes(validate(q, wrong_day, ds, cfg)) == ["V-14"]
    q = p.model_copy(deep=True)
    q.days[2].window = ["09:00", "18:00"]
    assert "V-15" in codes(validate(q, req, ds, cfg))
    forced = req.model_copy(update={"transport": req.transport.model_copy(update={"ret": req.transport.out})})
    q = p.model_copy(deep=True)
    q.request_hash = forced.request_hash()
    if (p.transport.return_.mode, p.transport.return_.class_) != ("train", "3A"):
        assert codes(validate(q, forced, ds, cfg)) == ["V-16"]
