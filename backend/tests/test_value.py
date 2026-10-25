"""ENG-AT-04: value function unit tests (002 Spec §6, addendum A1), hand-computed to 0.01."""

import pytest

from tests.helpers import CFG, request
from tripwise import value
from tripwise.data import Attraction


def attr(tags, rating=4.0, crowd="low"):
    return Attraction("JAI-A-99", "JAI", "x", 0, 0, 60, 540, 1080, frozenset(), 0, tuple(tags), rating, crowd, False)


def test_primary_and_secondary_tags():
    p = request().prefs                                          # history 5, culture 3
    assert value.activity(attr(["history", "culture"]), p, CFG) == pytest.approx(80.0, abs=0.01)
    # culture primary (3/5 = 0.6), history secondary (1 × 0.6 = 0.6): match 0.6 → 80 × (0.2 + 0.48)
    assert value.activity(attr(["culture", "history"]), p, CFG) == pytest.approx(54.4, abs=0.01)
    assert value.activity(attr(["food"]), p, CFG) == pytest.approx(16.0, abs=0.01)   # no match keeps 20 %


def test_crowd_penalty():
    p = request(prefs={"avoid_crowds": True}).prefs
    assert value.activity(attr(["history"], crowd="high"), p, CFG) == pytest.approx(56.0, abs=0.01)
    assert value.activity(attr(["history"], crowd="medium"), p, CFG) == pytest.approx(68.0, abs=0.01)
    assert value.activity(attr(["history"], crowd="low"), p, CFG) == pytest.approx(80.0, abs=0.01)
    assert value.activity(attr(["history"], crowd="high"), request().prefs, CFG) == pytest.approx(80.0, abs=0.01)


def test_plan_value_with_hotel_term():
    # 100 + 15 × (0.6 + 0.9) / 2 + 5 × 1 − 0.05 × 120 + κ_h × tier value (κ_h from config)
    kh = CFG.variants["kappa_h"]
    assert value.plan(100, 0.6, 0.9, 1, 120, "mid", CFG) == pytest.approx(110.25 + kh * 0.5, abs=0.01)
    assert value.plan(100, 0.6, 0.9, 1, 120, "premium", CFG) == pytest.approx(110.25 + kh, abs=0.01)
    assert value.plan(100, 0.6, 0.9, 1, 120, "budget", CFG) == pytest.approx(110.25, abs=0.01)
