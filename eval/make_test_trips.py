"""Generate eval/test_trips.json: 30 test trips meeting 002 Spec §12 (ENG-FR-12, T14).

    python eval/make_test_trips.py

Budgets are calibrated from the engine's exact minimum budget (002 Spec §8.2) for each trip:
tight = min × TIGHT (within 15 %), medium = min × MEDIUM, generous = min × GENEROUS, infeasible = min × LOW,
each rounded to 500. Locks and excludes are picked from the data. The script checks every coverage rule
before writing.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tripwise import config, data, engine  # noqa: E402
from tripwise.models import TripRequest  # noqa: E402
from tripwise.prefilter import fits  # noqa: E402
from tripwise.timemodel import day_windows  # noqa: E402

TIGHT, MEDIUM, GENEROUS, LOW = 1.08, 1.6, 2.6, 0.8
STEP = 500
PROFILES = {
    "heritage": {"nature": 1, "adventure": 0, "food": 3, "history": 5, "culture": 4, "spiritual": 2, "shopping": 2, "relaxation": 1, "nightlife": 0},
    "nature":   {"nature": 5, "adventure": 3, "food": 2, "history": 1, "culture": 1, "spiritual": 1, "shopping": 0, "relaxation": 4, "nightlife": 0},
    "city":     {"nature": 1, "adventure": 0, "food": 5, "history": 3, "culture": 4, "spiritual": 0, "shopping": 3, "relaxation": 1, "nightlife": 4},
    "spirit":   {"nature": 2, "adventure": 1, "food": 2, "history": 3, "culture": 3, "spiritual": 5, "shopping": 1, "relaxation": 3, "nightlife": 0},
    "beach":    {"nature": 3, "adventure": 3, "food": 4, "history": 1, "culture": 1, "spiritual": 0, "shopping": 2, "relaxation": 5, "nightlife": 4},
}
# id, origin, destination, start, days, people, pace, comfort, hours, budget kind, profile, extras
SPECS = [
    ("T01", "BLR", "JAI", "2026-12-18", 4, 2, "balanced", "mid", 9, "generous", "heritage", {"modes": {"bus": "avoid"}}),
    ("T02", "DEL", "AGR", "2026-12-14", 2, 1, "relaxed", "budget", 8, "tight", "heritage", {}),
    ("T03", "BOM", "GOA", "2027-01-08", 5, 3, "packed", "mid", 10, "medium", "beach", {}),
    ("T04", "CCU", "DJL", "2027-02-10", 4, 4, "balanced", "premium", 9, "generous", "nature", {"avoid_crowds": True}),
    ("T05", "MAA", "PDY", "2027-01-22", 3, 2, "relaxed", "budget", 8, "tight", "beach", {}),
    ("T06", "DEL", "VNS", "2027-01-04", 3, 6, "balanced", "budget", 9, "medium", "spirit", {}),
    ("T07", "HYD", "GOA", "2027-03-05", 6, 2, "packed", "premium", 12, "generous", "beach", {"modes": {"train": "avoid"}}),
    ("T08", "BLR", "MUN", "2026-12-26", 4, 1, "relaxed", "mid", 8, "tight", "nature", {"exclude": 1}),
    ("T09", "JAI", "RSH", "2027-02-17", 3, 2, "balanced", "mid", 10, "medium", "spirit", {"lock": 1}),
    ("T10", "DEL", "MAA", "2027-01-15", 5, 4, "packed", "mid", 11, "generous", "city", {}),
    ("T11", "CCU", "HYD", "2027-03-10", 7, 2, "relaxed", "premium", 8, "generous", "city", {}),
    ("T12", "AGR", "VNS", "2027-02-24", 2, 3, "packed", "budget", 12, "tight", "spirit", {}),
    ("T13", "BOM", "DEL", "2026-12-30", 4, 2, "balanced", "premium", 9, "medium", "heritage", {"avoid_crowds": True, "modes": {"bus": "avoid"}}),
    ("T14", "GOA", "HMP", "2027-02-01", 3, 1, "relaxed", "budget", 8, "tight", "heritage", {}),
    ("T15", "BLR", "HYD", "2027-01-27", 5, 6, "balanced", "mid", 9, "medium", "city", {}),
    ("T16", "PDY", "MUN", "2026-12-12", 6, 3, "relaxed", "mid", 9, "generous", "nature", {"lock": 2}),
    ("T17", "DEL", "JAI", "2027-03-19", 2, 2, "packed", "premium", 12, "tight", "heritage", {"modes": {"bus": "avoid"}}),
    ("T18", "MAA", "HYD", "2027-02-05", 3, 4, "packed", "budget", 10, "medium", "city", {"exclude": 2}),
    ("T19", "BLR", "GOA", "2027-01-11", 7, 2, "balanced", "budget", 9, "generous", "beach", {}),
    ("T20", "HYD", "VNS", "2027-03-26", 4, 1, "packed", "premium", 11, "medium", "spirit", {"avoid_crowds": True}),
    ("T21", "RSH", "DEL", "2026-12-21", 3, 2, "balanced", "mid", 9, "tight", "city", {"lock": 1}),
    ("T22", "VNS", "CCU", "2027-01-29", 5, 2, "relaxed", "premium", 8, "medium", "city", {"exclude": 1}),
    ("T23", "BOM", "HMP", "2027-02-12", 6, 4, "packed", "budget", 10, "tight", "heritage", {}),
    ("T24", "DJL", "CCU", "2027-03-01", 3, 6, "relaxed", "mid", 9, "generous", "city", {}),
    ("T25", "BLR", "DEL", "2027-01-20", 4, 2, "balanced", "mid", 9, "infeasible", "heritage", {}),
    ("T26", "GOA", "BOM", "2027-02-19", 3, 3, "packed", "premium", 10, "infeasible", "city", {}),
    ("T27", "JAI", "AGR", "2026-12-28", 5, 1, "relaxed", "budget", 8, "infeasible", "heritage", {}),
    ("T28", "BOM", "GOA", "2026-12-14", 2, 2, "balanced", "mid", 9, "generous", "beach", {"lock_impossible": "GOA-A-30"}),
    ("T29", "HMP", "MAA", "2027-01-06", 7, 3, "balanced", "mid", 9, "medium", "city", {}),
    ("T30", "AGR", "DEL", "2027-01-11", 4, 2, "packed", "mid", 10, "generous", "heritage", {}),
]


def round_to(x: float, up: bool) -> int:
    return (math.ceil if up else math.floor)(x / STEP) * STEP


def body(spec, budget, locks=(), excludes=()) -> dict:
    tid, o, d, start, days, people, pace, comfort, hours, kind, prof, ex = spec
    end = (date.fromisoformat(start) + timedelta(days=days - 1)).isoformat()
    return {"origin": o, "destination": d, "start_date": start, "end_date": end, "people": people, "budget_total": budget,
            "prefs": {"daily_hours_out": hours, "interests": PROFILES[prof], "pace": pace, "comfort": comfort,
                      "modes": ex.get("modes", {}), "avoid_crowds": ex.get("avoid_crowds", False)},
            "locks": list(locks), "excludes": list(excludes)}


def main() -> int:
    ds, cfg = data.default(), config.default()
    trips = []
    for spec in SPECS:
        tid, o, d, start, days, people, pace, comfort, hours, kind, prof, ex = spec
        probe = TripRequest.model_validate(body(spec, 10_000_000))
        ctx = engine.setup(probe, ds, cfg)
        assert isinstance(ctx, engine.Context), (tid, ctx)
        ranked = sorted(ctx.filt.kept, key=lambda a: (-ctx.v_all[a.attraction_id], a.attraction_id))
        locks, excludes, notes = [], [], []
        if ex.get("exclude"):
            excludes = [a.attraction_id for a in ranked[:ex["exclude"]]]
            notes.append(f"excludes the top {ex['exclude']} by value")
        if ex.get("lock"):
            # lock schedulable attractions just below the top ones, so the lock changes the plan
            best = min(range(len(ctx.outs)), key=lambda i: ctx.cand.out_cost[i])
            wins = day_windows(probe, cfg, ctx.outs[best], ctx.rets[min(range(len(ctx.rets)), key=lambda i: ctx.cand.ret_cost[i])])
            pool = [a for a in ranked[6:] if any(fits(a, w) for w in wins)]
            locks = [a.attraction_id for a in pool[:ex["lock"]]]
            notes.append(f"locks {', '.join(locks)}")
        if ex.get("lock_impossible"):
            locks = [ex["lock_impossible"]]
            notes.append(f"locks {locks[0]}, which is not open on any trip day")
        req = TripRequest.model_validate(body(spec, 10_000_000, locks, excludes))
        expect = "ok"
        if ex.get("lock_impossible"):
            budget = 200_000
            expect = "lock_impossible"
        else:
            rctx = engine.setup(req, ds, cfg)
            ch = engine.cheapest(rctx, engine.hotels_for(ds, req, engine.tiers_for(req)))
            mb = engine.min_budget_total(ch.cost, cfg)
            factor = {"tight": TIGHT, "medium": MEDIUM, "generous": GENEROUS, "infeasible": LOW}[kind]
            budget = round_to(mb * factor, up=kind != "infeasible")
            if kind == "infeasible":
                expect = "budget"
            notes.insert(0, f"{kind} budget (minimum {mb})")
        modes = ex.get("modes", {})
        if modes:
            notes.append("avoids " + ", ".join(m for m, v in modes.items() if v == "avoid"))
        if ex.get("avoid_crowds"):
            notes.append("avoids crowds")
        trips.append({"id": tid, "note": f"{o}-{d}, {days} days, {people} people, {pace}, {comfort}: " + "; ".join(notes),
                      "expect": expect, "budget_kind": kind, "request": body(spec, budget, locks, excludes)})
    check(trips, ds, cfg)
    out = ROOT / "eval" / "test_trips.json"
    out.write_text(json.dumps(trips, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", out.relative_to(ROOT), len(trips), "trips")
    return 0


def check(trips, ds, cfg) -> None:
    """002 Spec §12 coverage rules."""
    from tripwise.timemodel import options
    reqs = [TripRequest.model_validate(t["request"]) for t in trips]
    kinds = [t["budget_kind"] for t in trips]
    rules = {
        "30 trips": len(trips) == 30,
        "≥ 10 destinations": len({r.destination for r in reqs}) >= 10,
        "≥ 15 pairs": len({frozenset((r.origin, r.destination)) for r in reqs}) >= 15,
        "lengths 2-7": {r.days for r in reqs} >= set(range(2, 8)),
        "groups 1,2,3,4,6": {r.people for r in reqs} >= {1, 2, 3, 4, 6},
        "each pace ≥ 5": all(sum(r.prefs.pace == p for r in reqs) >= 5 for p in ("relaxed", "balanced", "packed")),
        "each comfort ≥ 5": all(sum(r.prefs.comfort == c for r in reqs) >= 5 for c in ("budget", "mid", "premium")),
        "≥ 5 include a Monday": sum(any((r.start_date + timedelta(days=i)).weekday() == 0 for i in range(r.days))
                                    for r in reqs) >= 5,
        "≥ 3 overnight-eligible pairs": len({frozenset((r.origin, r.destination)) for r in reqs
                                             if any(o.overnight for o in options(ds, cfg, r, "out"))}) >= 3,
        "≥ 3 flight-only pairs": len({frozenset((r.origin, r.destination)) for r in reqs
                                      if {o.mode for o in options(ds, cfg, r, "out")} == {"flight"}}) >= 3,
        "≥ 3 with a mode avoided": sum(any(v == "avoid" for v in r.prefs.modes.values()) for r in reqs) >= 3,
        "≥ 3 avoid crowds": sum(r.prefs.avoid_crowds for r in reqs) >= 3,
        "≥ 8 tight, 8 medium, 8 generous": all(kinds.count(k) >= 8 for k in ("tight", "medium", "generous")),
        "≥ 3 infeasible budget": sum(t["expect"] == "budget" for t in trips) >= 3,
        "≥ 1 impossible lock": sum(t["expect"] == "lock_impossible" for t in trips) >= 1,
        "≥ 3 with locks": sum(bool(r.locks) and t["expect"] == "ok" for r, t in zip(reqs, trips)) >= 3,
        "≥ 3 with excludes": sum(bool(r.excludes) for r in reqs) >= 3,
        "dates Dec 2026 - Mar 2027": all(date(2026, 12, 1) <= r.start_date and r.end_date <= date(2027, 3, 31) for r in reqs),
    }
    failed = [k for k, v in rules.items() if not v]
    for k, v in rules.items():
        print(("ok   " if v else "FAIL ") + k)
    assert not failed, failed


if __name__ == "__main__":
    sys.exit(main())
