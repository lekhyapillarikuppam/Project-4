"""Budget trade-offs for one variant (002 Spec addendum A4; FR-023, FR-025).

The variant's objective is re-run at budget × each of tradeoff_factors (computed on request, outside the
NFR-001 variant budget). Every figure comes from re-running the engine.
"""

from __future__ import annotations

from tripwise import config as config_mod
from tripwise import data as data_mod
from tripwise.config import Config
from tripwise.data import Dataset, round_half_up
from tripwise.engine import Context, setup
from tripwise.models import Plan, TradeOffRow, TradeOffs, TripRequest
from tripwise.variants import variant_plans


def variant_at(req: TripRequest, variant: str, ds: Dataset, cfg: Config):
    """The named variant's plan for this request (before the difference rule), or the infeasible result."""
    ctx = setup(req, ds, cfg)
    if not isinstance(ctx, Context):
        return ctx
    plans = variant_plans(ctx)
    return plans.get("error") or plans[variant]


def _journeys(p: Plan) -> str:
    o, r = p.transport.outbound, p.transport.return_
    return f"{o.mode} {o.class_} / {r.mode} {r.class_}"


def trade_offs(req: TripRequest, variant: str, ds: Dataset | None = None, cfg: Config | None = None):
    cfg = cfg or config_mod.default()
    ds = ds or data_mod.load_cached(str(cfg.data_dir))
    base = variant_at(req, variant, ds, cfg)
    if not isinstance(base, Plan):
        return base
    ids = set(base.activity_ids())
    rows = []
    for f in cfg.tradeoff_factors:
        b = round_half_up(req.budget_total * f)
        res = variant_at(req.model_copy(update={"budget_total": b}), variant, ds, cfg)
        if not isinstance(res, Plan):
            rows.append(TradeOffRow(factor=f, budget_total=b, status=getattr(res, "reason", res.status)))
            continue
        new = set(res.activity_ids())
        rows.append(TradeOffRow(
            factor=f, budget_total=b, status="ok", delta_cost=res.budget.total - base.budget.total,
            delta_value=round(res.value - base.value, 2), added=sorted(new - ids), dropped=sorted(ids - new),
            hotel_change=None if res.hotel.hotel_id == base.hotel.hotel_id else [base.hotel.hotel_id, res.hotel.hotel_id],
            transport_change=None if _journeys(res) == _journeys(base) else [_journeys(base), _journeys(res)]))
    return TradeOffs(variant=variant, budget_total=req.budget_total, cost=base.budget.total, value=base.value, rows=rows)
