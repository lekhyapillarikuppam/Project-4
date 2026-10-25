"""008 T01: the greedy baseline gives validator-clean plans; the LLM-only rebuild reproduces a plan from its choices,
times a day that does not fit naively (so the validator flags it) and rejects unknown ids. No Groq calls."""

import json
import sys
import time
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[2] / "eval"
sys.path.insert(0, str(EVAL))

from baselines import greedy, llm_only  # noqa: E402
from tripwise import config, data, engine  # noqa: E402
from tripwise.models import Plan, TripRequest  # noqa: E402
from validator.validate import validate  # noqa: E402

TRIPS = json.loads((EVAL / "test_trips.json").read_text(encoding="utf-8"))


def test_greedy_plans_validate():
    ds, cfg = data.default(), config.default()
    for t in TRIPS:
        req = TripRequest.model_validate(t["request"])
        p = greedy.plan(req)
        if t["expect"] == "ok":
            assert isinstance(p, Plan), t["id"]
            assert validate(p, req, ds, cfg.as_dict()) == [], t["id"]
        else:
            assert not isinstance(p, Plan), t["id"]


def test_llm_only_rebuild():
    ds, cfg = data.default(), config.default()
    t = next(t for t in TRIPS if t["expect"] == "ok")
    req = TripRequest.model_validate(t["request"])
    ctx = engine.setup(req, ds, cfg)
    g = greedy.plan(req)
    choice = {"outbound": 0, "return": 0, "hotel_id": g.hotel.hotel_id,
              "days": [{"day": d.day, "stops": [s.attraction_id for s in d.stops]} for d in g.days]}
    p = llm_only.realise(ctx, choice, time.perf_counter())
    assert p.value == g.value and validate(p, req, ds, cfg.as_dict()) == []
    text, top = llm_only.prompt(ctx)
    assert len(top) == llm_only.TOP_N and len(text) < 6000 * 3      # well under ~6,000 tokens
    crammed = choice | {"days": [{"day": 1, "stops": [a.attraction_id for a in top[:8]]}]}
    bad = validate(llm_only.realise(ctx, crammed, time.perf_counter()), req, ds, cfg.as_dict())
    assert bad                                                       # too much on day 1: the validator says so
    with pytest.raises(llm_only.Failed):
        llm_only.realise(ctx, choice | {"hotel_id": "NOPE"}, time.perf_counter())
    with pytest.raises(llm_only.Failed):
        llm_only.realise(ctx, choice | {"days": [{"day": 1, "stops": ["XXX-A-99"]}]}, time.perf_counter())
