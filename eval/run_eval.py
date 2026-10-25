"""Evaluation (008 EVAL-FR-01–EVAL-FR-04): Tripwise vs greedy vs LLM-only on eval/test_trips.json.

    python eval/run_eval.py            # Tripwise and greedy on all 30; LLM-only reused from eval/out/llm_only.json if present
    python eval/run_eval.py --llm      # (re)run the LLM-only baseline on its 10 trips first (Groq, 1 call a minute)

Writes eval/out/results.csv, three charts (eval/charts/feasibility.png, value.png, travel_share.png) and
eval/RESULTS.md. Tripwise and greedy are deterministic: a re-run gives the same numbers (EVAL-AT-02); solve times
are reported but not compared.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))

from baselines import greedy, llm_only  # noqa: E402
from api.ai import groq_client  # noqa: E402
from tripwise import config, data, engine  # noqa: E402
from tripwise.models import Plan, TripRequest  # noqa: E402
from tripwise.variants import plan_variants  # noqa: E402
from validator.validate import validate  # noqa: E402

OUT = ROOT / "eval" / "out"
CHARTS = ROOT / "eval" / "charts"
PLANNERS = ("tripwise", "greedy", "llm_only")
LABEL = {"tripwise": "Tripwise", "greedy": "Greedy", "llm_only": "LLM-only"}
COLOUR = {"tripwise": "#2a78d6", "greedy": "#eb6834", "llm_only": "#1baf7a"}   # validated categorical slots 1-3
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e2da"


def llm_trips(trips: list[dict]) -> list[str]:
    """10 feasible trips: 3 tight, 4 medium, 3 generous (first by id), fixed."""
    want = {"tight": 3, "medium": 4, "generous": 3}
    out = []
    for t in trips:
        if t["expect"] == "ok" and want.get(t["budget_kind"], 0) > 0:
            want[t["budget_kind"]] -= 1
            out.append(t["id"])
    return out


def travel_share(p: Plan) -> float | None:
    """Minutes on local rides ÷ minutes out of the hotel, over all days with activities."""
    ride = out = 0
    for d in p.days:
        if not d.stops:
            continue
        ride += sum(s.leg_from_prev.minutes for s in d.stops) + (d.return_leg.minutes if d.return_leg else 0)
        h, m = map(int, d.stops[0].arrive.split(":"))
        depart = h * 60 + m - d.stops[0].leg_from_prev.minutes
        h, m = map(int, d.stops[-1].end.split(":"))
        out += h * 60 + m + (d.return_leg.minutes if d.return_leg else 0) - depart
    return ride / out if out else None


def row(planner: str, t: dict, res, ms: float, ds, cfg, extra: dict | None = None) -> dict:
    req = TripRequest.model_validate(t["request"])
    r = {"planner": planner, "trip": t["id"], "budget_kind": t["budget_kind"], "expect": t["expect"],
         "status": "plan" if isinstance(res, Plan) else (getattr(res, "reason", None) or "failed"),
         "valid": False, "violations": "", "value": None, "cost": None, "usable": None, "budget_use": None,
         "travel_share": None, "stops": None, "solve_ms": round(ms), "variants": None}
    if isinstance(res, Plan):
        errs = validate(res, req, ds, cfg.as_dict())
        r |= {"valid": not errs, "violations": ";".join(sorted({e.split(":")[0] for e in errs})),
              "value": res.value, "cost": res.budget.total, "usable": res.budget.usable_budget,
              "budget_use": round(res.budget.total / res.budget.usable_budget, 4),
              "stops": sum(len(d.stops) for d in res.days),
              "travel_share": None if travel_share(res) is None else round(travel_share(res), 4)}
    return r | (extra or {})


def run_llm(trips: list[dict], ids: list[str]) -> list[dict]:
    """One Groq call per trip, paced 1 a minute; waits out free-tier refusals. Saved raw to llm_only.json."""
    saved = []
    for t in (t for t in trips if t["id"] in ids):
        req = TripRequest.model_validate(t["request"])
        for attempt in range(37):
            p, info = llm_only.plan(req)
            if not info.get("reason", "").startswith("groq unavailable"):
                break
            print(f"   {t['id']}: Groq refused; waiting 5 min", flush=True)
            time.sleep(300)
        saved.append({"trip": t["id"], "plan": p.model_dump(mode="json", by_alias=True) if isinstance(p, Plan) else None,
                      "info": info})
        (OUT / "llm_only.json").write_text(json.dumps(saved, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"   LLM-only {t['id']}: {'plan' if isinstance(p, Plan) else info.get('reason')} ({info.get('seconds')} s)", flush=True)
        time.sleep(60)
    return saved


def summarise(rows: list[dict], trip_ids: set[str]) -> dict:
    """planner -> metrics over the given trips (feasibility over feasible trips; infeasible trips separately)."""
    out = {}
    for pl in PLANNERS:
        rs = [r for r in rows if r["planner"] == pl and r["trip"] in trip_ids]
        if not rs:
            continue
        ok = [r for r in rs if r["expect"] == "ok"]
        bad = [r for r in rs if r["expect"] != "ok"]
        valid = [r for r in ok if r["valid"]]
        viol: dict[str, int] = {}
        for r in ok:
            for v in filter(None, r["violations"].split(";")):
                viol[v] = viol.get(v, 0) + 1
        mean = lambda xs: round(statistics.mean(xs), 3) if xs else None   # noqa: E731
        out[pl] = {
            "trips": len(rs), "feasible_trips": len(ok), "valid": len(valid),
            "feasibility": round(len(valid) / len(ok), 3) if ok else None,
            "failed": sum(r["status"] not in ("plan",) for r in ok),
            "violations": viol,
            "declined_infeasible": f"{sum(r['status'] != 'plan' for r in bad)}/{len(bad)}" if bad else "–",
            "mean_value": mean([r["value"] for r in valid]),
            "total_value": round(sum(r["value"] for r in valid), 1),
            "mean_budget_use": mean([r["budget_use"] for r in valid]),
            "mean_travel_share": mean([r["travel_share"] for r in valid if r["travel_share"] is not None]),
            "median_ms": round(statistics.median(r["solve_ms"] for r in rs)),
            "mean_variants": mean([r["variants"] for r in ok if r["variants"] is not None]),
        }
    return out


# --- charts --------------------------------------------------------------------------------------------------

def _axes(ax, title: str, ylabel: str):
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=10)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _grouped(ax, groups: list[str], series: dict[str, list], fmt):
    import numpy as np
    names = [p for p in PLANNERS if p in series]
    width = 0.8 / len(names)
    x = np.arange(len(groups))
    for i, p in enumerate(names):
        vals = series[p]
        pos = x - 0.4 + width * (i + 0.5)
        bars = ax.bar(pos, [v if v is not None else 0 for v in vals], width - 0.04, color=COLOUR[p], label=LABEL[p],
                      edgecolor="white", linewidth=2)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), "n/a" if v is None else fmt(v), ha="center",
                    va="bottom", fontsize=8, color=INK)
    ax.set_xticks(x, groups)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.12), ncol=3)


def charts(all30: dict, same10: dict, rows: list[dict], ten: list[str]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups = ["All 30 trips", "Same 10 trips"]

    def pair(key):
        return {p: [all30.get(p, {}).get(key), same10.get(p, {}).get(key)] for p in PLANNERS if p in same10}

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    _axes(ax, "Feasibility: share of feasible trips with a validator-clean plan", "share of trips")
    _grouped(ax, groups, pair("feasibility"), lambda v: f"{v:.0%}")
    ax.set_ylim(0, 1.12)
    fig.tight_layout()
    fig.savefig(CHARTS / "feasibility.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=150)
    _axes(ax, "Plan value per trip (valid plans only; higher is better)", "plan value")
    trips = sorted({r["trip"] for r in rows if r["expect"] == "ok"})
    for k, p in enumerate(PLANNERS):
        pts = [(i + (k - 1) * 0.18, r["value"]) for i, t in enumerate(trips) for r in rows
               if r["planner"] == p and r["trip"] == t and r["valid"]]
        if pts:
            ax.scatter([a for a, _ in pts], [b for _, b in pts], s=36, color=COLOUR[p], label=LABEL[p],
                       edgecolors="white", linewidths=1.5, zorder=3)
    ax.set_xticks(range(len(trips)), [t + ("*" if t in ten else "") for t in trips], rotation=90, fontsize=8)
    ax.set_xlabel("test trip (* = also run by LLM-only)", color=MUTED, fontsize=9)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.28), ncol=3)
    fig.tight_layout()
    fig.savefig(CHARTS / "value.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    _axes(ax, "Share of time out of the hotel spent on local travel (lower is better)", "mean share")
    _grouped(ax, groups, pair("mean_travel_share"), lambda v: f"{v:.0%}")
    ax.set_ylim(0, max(v or 0 for vs in pair("mean_travel_share").values() for v in vs) * 1.25 + 0.01)
    fig.tight_layout()
    fig.savefig(CHARTS / "travel_share.png")
    plt.close(fig)


# --- report --------------------------------------------------------------------------------------------------

def table(s: dict) -> str:
    head = ("| Planner | Feasible trips with a valid plan | Failed plans | Violations (V-xx: trips) | Declined infeasible "
            "| Mean value | Total value | Mean budget use | Mean travel share | Median time | Distinct variants |")
    lines = [head, "|" + "---|" * 11]
    for p, m in s.items():
        viol = ", ".join(f"{k}: {v}" for k, v in sorted(m["violations"].items())) or "none"
        pct = lambda v: "–" if v is None else f"{v:.0%}"   # noqa: E731
        lines.append(f"| {LABEL[p]} | {m['valid']}/{m['feasible_trips']} ({pct(m['feasibility'])}) | {m['failed']} | {viol} "
                     f"| {m['declined_infeasible']} | {m['mean_value'] or '–'} | {m['total_value']} | {pct(m['mean_budget_use'])} "
                     f"| {pct(m['mean_travel_share'])} | {m['median_ms']:,} ms | {m['mean_variants'] or '–'} |")
    return "\n".join(lines)


def main() -> int:
    ds, cfg = data.default(), config.default()
    OUT.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    trips = json.loads((ROOT / "eval" / "test_trips.json").read_text(encoding="utf-8"))
    ten = llm_trips(trips)
    rows = []
    for t in trips:
        req = TripRequest.model_validate(t["request"])
        t0 = time.perf_counter()
        p = engine.plan(req, ds, cfg)
        ms = (time.perf_counter() - t0) * 1000
        vr = plan_variants(req, ds, cfg)
        rows.append(row("tripwise", t, p, ms, ds, cfg, {"variants": len(vr.variants) if hasattr(vr, "variants") else 0}))
        t0 = time.perf_counter()
        g = greedy.plan(req, ds, cfg)
        rows.append(row("greedy", t, g, (time.perf_counter() - t0) * 1000, ds, cfg))
    llm_file = OUT / "llm_only.json"
    if "--llm" in sys.argv:
        saved = run_llm(trips, ten)
    else:                                   # reuse the stored LLM-only run (none yet: the tables leave it out)
        saved = json.loads(llm_file.read_text(encoding="utf-8")) if llm_file.exists() else []
    by_id = {t["id"]: t for t in trips}
    for s in saved:
        p = Plan.model_validate(s["plan"]) if s["plan"] else None
        rows.append(row("llm_only", by_id[s["trip"]], p, (s["info"].get("seconds") or 0) * 1000, ds, cfg,
                        {"status": "plan" if p else "failed"} if not p else None))
    with (OUT / "results.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    all30 = summarise([r for r in rows if r["planner"] != "llm_only"], {t["id"] for t in trips})
    same10 = summarise(rows, set(ten))
    charts(all30, same10, rows, ten)
    (OUT / "summary.json").write_text(json.dumps({"all30": all30, "same10": same10, "llm_trips": ten}, indent=1),
                                      encoding="utf-8")
    write_results(all30, same10, rows, ten)
    for name, s in (("all 30", all30), ("same 10", same10)):
        print(name)
        for p, m in s.items():
            print(f"  {LABEL[p]:9} valid {m['valid']}/{m['feasible_trips']}  mean value {m['mean_value']}  "
                  f"budget use {m['mean_budget_use']}  travel {m['mean_travel_share']}  viol {m['violations']}")
    ok = all30["tripwise"]["feasibility"] == 1.0
    return 0 if ok else 1


def write_results(all30: dict, same10: dict, rows: list[dict], ten: list[str]):
    ok = sorted({r["trip"] for r in rows if r["expect"] == "ok"})
    val = {(r["planner"], r["trip"]): r["value"] for r in rows if r["valid"]}
    won = [t for t in ok if (val.get(("greedy", t)) or 0) > (val.get(("tripwise", t)) or 0)]
    use = {(r["planner"], r["trip"]): r["budget_use"] for r in rows if r["valid"]}
    stops = {(r["planner"], r["trip"]): r["stops"] for r in rows if r["valid"]}
    mean = lambda xs: round(statistics.mean(xs), 2) if xs else "n/a"   # noqa: E731
    llm = same10.get("llm_only")
    discussion = DISCUSSION.format(
        tw=all30["tripwise"], gr=all30["greedy"], wins=len(won), n_ok=len(ok), won=", ".join(won) or "none",
        tw_use_won=mean([use[("tripwise", t)] for t in won]), gr_use_won=mean([use[("greedy", t)] for t in won]),
        tw_stops_won=mean([stops[("tripwise", t)] for t in won]), gr_stops_won=mean([stops[("greedy", t)] for t in won]),
        llm_line=(f"LLM-only produced valid plans for {llm['valid']}/{llm['feasible_trips']} of its trips ({llm['failed']} "
                  "could not be used at all); violations seen: "
                  + (", ".join(f"{k} ({v} trips)" for k, v in sorted(llm["violations"].items())) or "none")
                  + ". A plan written by a language model needs the engine's checks before it can be trusted.")
        if llm else "LLM-only has not been run yet (`python eval/run_eval.py --llm`).")
    text = f"""# Evaluation results (Feature 008)

Generated by `python eval/run_eval.py` on {time.strftime('%Y-%m-%d')} from `eval/test_trips.json` (30 trips: 26
feasible, 4 that must be reported infeasible). Raw rows: `eval/out/results.csv`. Charts: `eval/charts/feasibility.png`,
`eval/charts/value.png`, `eval/charts/travel_share.png`.

All three planners use the same data, time model, cost model and value function, and every plan is checked by the
same independent validator. "Tripwise" is the engine's single plan in the user's tier (`engine.plan`); "distinct
variants" counts the variants shown after the difference rule. Greedy and Tripwise run all 30 trips; LLM-only
(`openai/gpt-oss-120b`, one call per trip) runs 10 of them because of Groq free-tier limits: {', '.join(ten)}.

Budget use is the plan cost ÷ usable budget; travel share is local-ride minutes ÷ minutes out of the hotel. Means are
over valid plans. Times: Tripwise and greedy on this laptop; LLM-only includes the Groq round trip.

## All 30 trips (Tripwise, greedy)

{table(all30)}

## Same 10 trips (all three planners)

{table(same10)}

![Feasibility](charts/feasibility.png)
![Value per trip](charts/value.png)
![Travel share](charts/travel_share.png)

## Discussion

{discussion}

{HISTORY}
"""
    (ROOT / "eval" / "RESULTS.md").write_text(text, encoding="utf-8", newline="\n")


HISTORY = """## Before and after the fill step (2026-10-26)

After the first evaluation, greedy beat Tripwise on 8 of 26 trips. The engine gained a fill step (ENG-FR-13): after
exact routing it tries the unchosen candidates in descending value and keeps each one that still fits a day and
the budget (Experience and the single plan: any value gain; Balanced: ΔV − λ·V*·Δcost/B_u > 0; Saver: no fill).
A routing fix came with it: when every lock is mandatory and no first route exists, routing retries with locks as
very expensive drops instead of dropping every stop.

| Tripwise, all 30 trips | Before | After |
|---|---|---|
| Valid plans | 26/26 | 26/26 |
| Mean value | 684.7 | 729.5 |
| Trips where greedy scores higher | 8 of 26 (T04, T06, T07, T12, T16, T20, T21, T23) | 6 of 26 (T04, T06, T12, T16, T20, T23) |
| Mean budget use | 71.6% | 72.1% |
| Mean travel share | 15.2% | 15.6% |
| Single plan p95 / all variants p95 | 568 ms / 1,531 ms | 559 ms / 1,761 ms |

The fill closed most of the stop-count gap (T20: 15 → 24 stops, value 783 → 1,131; T07 now beats greedy). Where
greedy still wins, both planners usually have the same number of stops but greedy's are worth more (T06, T12:
12 against 12): stage 1 chose a lower-value set and the fill can only add, not swap. A swap step is the next
improvement."""


DISCUSSION = """- **Feasibility.** Tripwise returned a validator-clean plan for {tw[valid]}/{tw[feasible_trips]} feasible trips and
  correctly declined {tw[declined_infeasible]} infeasible ones. Greedy, built on the same time and cost functions, was
  also clean ({gr[valid]}/{gr[feasible_trips]}): feasibility comes from the shared model, not from the optimiser.
  {llm_line}
- **Value.** Tripwise's mean value is {tw[mean_value]} against greedy's {gr[mean_value]}, but greedy scored higher on
  {wins} of {n_ok} trips ({won}). On those trips greedy fits more activities ({gr_stops_won} against
  {tw_stops_won} on average) for about the same share of the budget ({gr_use_won} against {tw_use_won}): the engine selects
  activities in stage 1 on conservative estimates of time and cost and does not top up the plan after exact routing.
  Over all trips budget use is similar ({tw[mean_budget_use]} against {gr[mean_budget_use]}). A post-routing fill step
  is the clearest improvement to make next.
- **Travel.** Tripwise routes each day (OR-Tools), so a smaller share of the day goes on local rides
  ({tw[mean_travel_share]} against greedy's {gr[mean_travel_share]}).
- **Variants.** Tripwise showed {tw[mean_variants]} distinct variants per feasible trip on average.
- **Chat intents (EVAL-FR-03).** See AI-AT-03 in `eval/AI_AT_03.md`."""


if __name__ == "__main__":
    sys.exit(main())
