"""Command-line harness (002 Spec ENG-FR-11).

    python -m tripwise.cli plan <request.json> [--json]
    python -m tripwise.cli variants <request.json> [--json]
    python -m tripwise.cli tradeoffs <request.json> [--variant balanced] [--json]
    python -m tripwise.cli batch <test_trips.json> [--variants] [--repeat N]

Run from backend/ (or with backend/ on PYTHONPATH). A request file holds one TripRequest; a trips file is a
list of {"id", "note", "expect", "request"}.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from tripwise import config, data
from tripwise.engine import inr, plan
from tripwise.models import Infeasible, InternalError, Plan, TripRequest, VariantsResult, dump
from tripwise.tradeoffs import trade_offs
from tripwise.variants import plan_variants
from validator.validate import validate

WEEKDAY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def read_request(path: str) -> TripRequest:
    return TripRequest.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def show_plan(p: Plan) -> str:
    o, r = p.transport.outbound, p.transport.return_
    lines = [f"Plan{' (' + p.variant + ')' if p.variant else ''}: value {p.value}, total {inr(p.budget.total)} "
             f"of {inr(p.budget.usable_budget)} usable ({p.budget.estimate_label})",
             f"  Out:    {o.mode} {o.class_}, depart {o.depart}{' (overnight)' if o.overnight else ''}, "
             f"at the centre {o.arrive_centre}, {inr(o.cost)}",
             f"  Return: {r.mode} {r.class_}, leave the centre {r.leave_centre}, arrive {r.arrive_origin}"
             f"{' (overnight)' if r.overnight else ''}, {inr(r.cost)}",
             f"  Hotel:  {p.hotel.name} ({p.hotel.tier}), {p.hotel.nights} nights × {p.hotel.rooms} room(s), "
             f"{inr(p.hotel.cost)}"]
    for d in p.days:
        win = "–".join(d.window) if d.window else "no time for activities"
        lunch = f", lunch {d.lunch[0]}" if d.lunch else ""
        lines.append(f"  Day {d.day} {WEEKDAY[d.weekday]} {d.date}  window {win}{lunch}")
        for s in d.stops:
            lg = s.leg_from_prev
            lines.append(f"      {s.start}–{s.end}  {s.name}  (fee {inr(s.entry_cost)}; {lg.mode} {lg.minutes} min "
                         f"{lg.km} km {inr(lg.cost)})")
        if d.return_leg:
            lines.append(f"      back to the hotel: {d.return_leg.minutes} min, {inr(d.return_leg.cost)}")
    b = p.budget
    lines.append(f"  Budget: outbound {inr(b.outbound)}, return {inr(b.return_)}, stay {inr(b.stay)}, food {inr(b.food)}, "
                 f"entry {inr(b.entry_fees)}, local {inr(b.local_travel)} = {inr(b.total)}; contingency {inr(b.contingency)}")
    if p.near_misses:
        lines.append("  Near misses: " + "; ".join(f"{n.name} ({n.reason})" for n in p.near_misses))
    lines.append(f"  Solver: {p.solver.hotel_candidates} hotels, {p.solver.feedback_iters} feedback rounds, "
                 f"{p.solver.repairs} repairs, {p.solver.solve_ms} ms")
    return "\n".join(lines)


def show(result) -> str:
    if isinstance(result, Plan):
        return show_plan(result)
    if isinstance(result, VariantsResult):
        parts = [show_plan(p) for p in result.variants]
        parts += [f"Not shown: {d.name} ({d.reason})" for d in result.dropped]
        return "\n\n".join(parts)
    if isinstance(result, Infeasible):
        return f"No plan: {result.message} [{result.reason}]"
    if isinstance(result, InternalError):
        return "Internal error, plan withheld: " + "; ".join(result.failures)
    return json.dumps(dump(result), indent=1, ensure_ascii=False)


def status_of(result) -> str:
    return "ok" if isinstance(result, (Plan, VariantsResult)) else getattr(result, "reason", "error")


def batch(path: str, variants: bool, repeat: int) -> int:
    trips = json.loads(Path(path).read_text(encoding="utf-8"))
    ds, cfg = data.default(), config.default()
    fn = plan_variants if variants else plan
    print(f"{'id':<5} {'expect':<16} {'status':<16} {'n':>2} {'cost':>9} {'value':>8} {'ms':>6}  validator")
    times, bad = [], 0
    for t in trips:
        req = TripRequest.model_validate(t["request"])
        best_ms = None
        for _ in range(repeat):
            t0 = time.perf_counter()
            res = fn(req, ds, cfg)
            ms = (time.perf_counter() - t0) * 1000
            best_ms = ms if best_ms is None else min(best_ms, ms)
        times.append(best_ms)
        plans = res.variants if isinstance(res, VariantsResult) else [res] if isinstance(res, Plan) else []
        fails = [f for p in plans for f in validate(p, req, ds, cfg.as_dict())]
        status = status_of(res)
        ok = status == t["expect"] and not fails
        bad += not ok
        cost = plans[0].budget.total if plans else (getattr(res, "min_budget_total", None) or "")
        val = plans[0].value if plans else ""
        print(f"{t['id']:<5} {t['expect']:<16} {status:<16} {len(plans):>2} {cost!s:>9} {val!s:>8} {best_ms:>6.0f}  "
              f"{'pass' if not fails else 'FAIL ' + '; '.join(fails)}{'' if ok else '  <-- MISMATCH'}")
    times.sort()
    p95 = times[min(len(times) - 1, int(round(0.95 * len(times) + 0.5)) - 1)]
    print(f"\n{len(trips)} trips, {len(trips) - bad} match their expectation; solve ms median "
          f"{statistics.median(times):.0f}, p95 {p95:.0f}, max {times[-1]:.0f}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m tripwise.cli", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "variants", "tradeoffs"):
        s = sub.add_parser(name)
        s.add_argument("request")
        s.add_argument("--json", action="store_true")
        if name == "tradeoffs":
            s.add_argument("--variant", default="balanced", choices=["experience", "balanced", "saver"])
    b = sub.add_parser("batch")
    b.add_argument("trips")
    b.add_argument("--variants", action="store_true")
    b.add_argument("--repeat", type=int, default=1, help="run each trip N times and report the fastest")
    args = ap.parse_args(argv)
    if args.cmd == "batch":
        return batch(args.trips, args.variants, args.repeat)
    req = read_request(args.request)
    if args.cmd == "plan":
        res = plan(req)
    elif args.cmd == "variants":
        res = plan_variants(req)
    else:
        res = trade_offs(req, args.variant)
    print(json.dumps(dump(res), indent=1, ensure_ascii=False) if args.json else show(res))
    return 0 if status_of(res) == "ok" or not isinstance(res, InternalError) else 1


if __name__ == "__main__":
    sys.exit(main())
