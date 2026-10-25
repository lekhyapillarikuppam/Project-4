"""Acceptance tests over eval/test_trips.json (002 Spec §14 and addendum A7). Marked slow.

ENG-AT-01, ENG-AT-06, ENG-AT-07, ENG-AT-08, ENG-AT-09, VAR-AT-01, VAR-AT-02, VAR-AT-03, VAR-AT-04.
Timings are measured on this machine (the developer laptop) and printed with -s.
"""

import copy
import json
import time
from pathlib import Path

import pytest

from tripwise import config, data, engine
from tripwise.models import Infeasible, Plan, TripRequest, VariantsResult, dump
from tripwise.tradeoffs import trade_offs, variant_at
from tripwise.variants import distinct, plan_variants, variant_plans
from validator.validate import validate

pytestmark = pytest.mark.slow
TRIPS = json.loads((Path(__file__).resolve().parents[2] / "eval" / "test_trips.json").read_text(encoding="utf-8"))
OK = [t for t in TRIPS if t["expect"] == "ok"]


def p95(xs):
    xs = sorted(xs)
    return xs[max(0, -(-95 * len(xs) // 100) - 1)]


@pytest.fixture(scope="module")
def env():
    return data.default(), config.default()


@pytest.fixture(scope="module")
def singles(env):
    ds, cfg = env
    out = {}
    for t in TRIPS:
        req = TripRequest.model_validate(t["request"])
        t0 = time.perf_counter()
        res = engine.plan(req, ds, cfg)
        out[t["id"]] = (req, res, (time.perf_counter() - t0) * 1000)
    return out


@pytest.fixture(scope="module")
def variants(env):
    ds, cfg = env
    out = {}
    for t in OK:
        req = TripRequest.model_validate(t["request"])
        t0 = time.perf_counter()
        res = plan_variants(req, ds, cfg)
        out[t["id"]] = (req, res, (time.perf_counter() - t0) * 1000)
    return out


def strip(d):
    """A plan dict without solve_ms."""
    d = copy.deepcopy(d)
    for p in d.get("variants", [d]):
        p.get("solver", {}).pop("solve_ms", None)
    return d


def test_eng_at_01_batch(env, singles):
    ds, cfg = env
    for t in TRIPS:
        req, res, _ = singles[t["id"]]
        status = "ok" if isinstance(res, Plan) else getattr(res, "reason", "error")
        assert status == t["expect"], (t["id"], dump(res))
        if isinstance(res, Plan):
            assert validate(res, req, ds, cfg.as_dict()) == [], t["id"]


def test_eng_at_06_repeatable(env, singles):
    ds, cfg = env
    for t in OK:
        req, first, _ = singles[t["id"]]
        again = engine.plan(req, ds, cfg)
        assert strip(dump(again)) == strip(dump(first)), t["id"]


def test_eng_at_07_min_budget_round_trip(env, singles):
    ds, cfg = env
    infeasible = [t for t in TRIPS if t["expect"] == "budget"]
    assert len(infeasible) >= 3
    for t in infeasible:
        req, res, _ = singles[t["id"]]
        assert isinstance(res, Infeasible) and res.min_budget_total
        again = engine.plan(req.model_copy(update={"budget_total": res.min_budget_total}), ds, cfg)
        assert isinstance(again, Plan), (t["id"], dump(again))


def test_eng_at_08_single_plan_timing(singles):
    times = [ms for _, _, ms in singles.values()]
    print(f"\nENG-AT-08 single plan over {len(times)} trips: p95 {p95(times):.0f} ms, max {max(times):.0f} ms")
    assert p95(times) <= 2500


def test_eng_at_09_config_change(env):
    ds, cfg = env
    req = TripRequest.model_validate(OK[0]["request"])
    base = engine.plan(req, ds, cfg)
    raw = copy.deepcopy(cfg.as_dict())
    raw["value"]["kappa_t"] = 40
    raw["value"]["mu_travel_per_min"] = 0.5
    changed = engine.plan(req, ds, config.Config(raw, cfg.path))
    assert isinstance(base, Plan) and isinstance(changed, Plan)
    assert strip(dump(changed)) != strip(dump(base))


def test_var_at_01_variants(env, variants):
    ds, cfg = env
    for tid, (req, res, _) in variants.items():
        assert isinstance(res, VariantsResult), (tid, dump(res))
        assert 1 <= len(res.variants) <= 3, tid
        assert len(res.variants) + len(res.dropped) == 3, tid
        for i, a in enumerate(res.variants):
            assert validate(a, req, ds, cfg.as_dict()) == [], (tid, a.variant)
            for b in res.variants[i + 1:]:
                assert distinct(a, b, cfg.variants["difference"]), (tid, a.variant, b.variant)


def test_var_at_02_ordering(env):
    ds, cfg = env
    for t in OK:
        ctx = engine.setup(TripRequest.model_validate(t["request"]), ds, cfg)
        v = variant_plans(ctx)
        e, b, s = v["experience"], v["balanced"], v["saver"]
        assert s.budget.total <= b.budget.total <= e.budget.total, t["id"]
        assert s.value >= cfg.variants["rho"] * e.value - 1e-9, t["id"]


def test_var_at_03_variants_timing(variants):
    times = [ms for _, _, ms in variants.values()]
    print(f"\nVAR-AT-03 all variants over {len(times)} trips: p95 {p95(times):.0f} ms, max {max(times):.0f} ms")
    assert p95(times) <= 5000


def test_var_at_04_tradeoffs(env):
    ds, cfg = env
    for t in OK[:5]:
        req = TripRequest.model_validate(t["request"])
        to = trade_offs(req, "balanced", ds, cfg)
        base = variant_at(req, "balanced", ds, cfg)
        assert (to.cost, to.value) == (base.budget.total, base.value), t["id"]
        for row in to.rows:
            res = variant_at(req.model_copy(update={"budget_total": row.budget_total}), "balanced", ds, cfg)
            if row.status != "ok":
                assert not isinstance(res, Plan) and res.reason == row.status, t["id"]
                continue
            assert row.delta_cost == res.budget.total - base.budget.total, (t["id"], row.factor)
            assert row.delta_value == round(res.value - base.value, 2), (t["id"], row.factor)
            assert row.added == sorted(set(res.activity_ids()) - set(base.activity_ids()))
            assert row.dropped == sorted(set(base.activity_ids()) - set(res.activity_ids()))
