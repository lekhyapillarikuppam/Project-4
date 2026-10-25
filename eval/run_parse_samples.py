"""AI-AT-01: run the 10 free-text samples through /ai/parse-prefs logic and check them.

    python eval/run_parse_samples.py   (needs GROQ_API_KEY)

"Valid" = the parser returned output that passes the prefs schema (it raises otherwise). "Sensible" is judged
by hand from the printed output; the listed expectations are the reviewer's checklist and are checked too.
Writes eval/out/parse_samples.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from api.ai import parse  # noqa: E402


def check(out: dict, exp: dict) -> list[str]:
    p = out["prefs"]
    misses = []
    for t in exp.get("high", []):
        if p["interests"][t] < 4:
            misses.append(f"{t} weight {p['interests'][t]} < 4")
    for t in exp.get("low", []):
        if p["interests"][t] > 1:
            misses.append(f"{t} weight {p['interests'][t]} > 1")
    for k in ("pace", "comfort", "avoid_crowds"):
        if k in exp and p[k] != exp[k]:
            misses.append(f"{k} {p[k]} != {exp[k]}")
    for m, v in exp.get("modes", {}).items():
        if p["modes"][m] != v:
            misses.append(f"{m} {p['modes'][m]} != {v}")
    if "hours_max" in exp and p["daily_hours_out"] > exp["hours_max"]:
        misses.append(f"hours {p['daily_hours_out']} > {exp['hours_max']}")
    for k in ("origin", "destination", "people", "budget_total", "budget_per_person"):
        if k in exp and out.get(k) != exp[k]:
            misses.append(f"{k} {out.get(k)} != {exp[k]}")
    return misses


def main() -> int:
    samples = json.loads((ROOT / "eval" / "parse_samples.json").read_text(encoding="utf-8"))
    results, valid, sensible = [], 0, 0
    for s in samples:
        try:
            out = parse.parse(s["text"])
            valid += 1
            misses = check(out, s["expect"])
            sensible += not misses
        except Exception as exc:     # noqa: BLE001 — record any failure as invalid
            out, misses = {"error": type(exc).__name__}, ["invalid"]
        results.append({"id": s["id"], "text": s["text"], "output": out, "misses": misses})
        time.sleep(4)      # stay under the Groq free-tier tokens-per-minute limit
        print(s["id"], "OK" if not misses else "MISS: " + "; ".join(misses))
    (ROOT / "eval" / "out").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval" / "out" / "parse_samples.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"valid {valid}/{len(samples)}, checklist met {sensible}/{len(samples)}")
    return 0 if valid == len(samples) else 1


if __name__ == "__main__":
    sys.exit(main())
