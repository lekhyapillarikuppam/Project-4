"""Variants Experience → Balanced → Saver and the difference rule (002 Spec addendum A2, A3, A6).

Each variant runs the full pipeline (engine.run). Experience runs first because the others need V*.
Ordering guarantees (VAR-AT-02), applied before the difference rule:
- Saver must reach V ≥ ρ × V* on its routed plan: it is re-run with a raised target up to saver_retries times,
  and otherwise (or if it costs more than Experience) takes the Experience plan;
- a Balanced plan costing more than Experience takes the Experience plan; a Balanced plan below ρ × V* takes
  the Saver plan; a Saver costing more than Balanced takes the Balanced plan.
A variant that took another's plan is then dropped as "same as …".
"""

from __future__ import annotations

import time

from tripwise import config as config_mod
from tripwise import data as data_mod
from tripwise.config import Config
from tripwise.data import Dataset
from tripwise.engine import Context, hotels_for, run, setup, tiers_for
from tripwise.models import Dropped, Plan, TripRequest, VariantsResult

ORDER = ("experience", "balanced", "saver")


def _as(plan: Plan, name: str) -> Plan:
    p = plan.model_copy(deep=True)
    p.variant = name
    return p


def variant_plans(ctx: Context) -> dict:
    """name -> Plan (after the ordering fallbacks), or {"error": result} when Experience is not a Plan."""
    req, cfg = ctx.req, ctx.cfg
    exp = run(ctx, "max_value", hotels_for(ctx.ds, req, tiers_for(req, +1)), variant="experience").result
    if not isinstance(exp, Plan):
        return {"error": exp}
    vstar = exp.value
    bal = run(ctx, "balanced", hotels_for(ctx.ds, req, tiers_for(req)), vstar=vstar, variant="balanced").result
    if not isinstance(bal, Plan) or bal.budget.total > exp.budget.total:
        bal = _as(exp, "balanced")
    rho = cfg.variants["rho"]
    floor = rho * vstar
    target = vstar
    sav = None
    for _ in range(1 + cfg.variants["saver_retries"]):
        s = run(ctx, "min_cost", hotels_for(ctx.ds, req, tiers_for(req, -1)), vstar=target, variant="saver").result
        if not isinstance(s, Plan):
            break
        if s.value >= floor:
            sav = s
            break
        target += (floor - s.value) / rho + 1e-6
    if sav is None or sav.budget.total > exp.budget.total:
        sav = _as(exp, "saver")          # Experience always reaches the floor
    if bal.value < floor:                # a Balanced plan below the Saver floor takes the Saver plan
        bal = _as(sav, "balanced")
    if sav.budget.total > bal.budget.total:
        sav = _as(bal, "saver")
    return {"experience": exp, "balanced": bal, "saver": sav}


def distinct(a: Plan, b: Plan, share: float) -> bool:
    if a.hotel.hotel_id != b.hotel.hotel_id:
        return True
    sa, sb = set(a.activity_ids()), set(b.activity_ids())
    union = sa | sb
    return bool(union) and len(sa ^ sb) / len(union) >= share


def plan_variants(req: TripRequest, ds: Dataset | None = None, cfg: Config | None = None):
    cfg = cfg or config_mod.default()
    ds = ds or data_mod.load_cached(str(cfg.data_dir))
    ctx = setup(req, ds, cfg)
    if not isinstance(ctx, Context):
        return ctx
    plans = variant_plans(ctx)
    if "error" in plans:
        return plans["error"]
    kept, dropped = [], []
    for name in ORDER:
        p = plans[name]
        same = next((k for k in kept if not distinct(p, k, cfg.variants["difference"])), None)
        if same is None:
            kept.append(p)
        else:
            dropped.append(Dropped(name=name, reason=f"same as {same.variant.capitalize()}"))
    return VariantsResult(variants=kept, dropped=dropped)
