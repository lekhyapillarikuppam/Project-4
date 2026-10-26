"""AI-AT-02: explanations for 10 test trips (the first 10 feasible trips in eval/test_trips.json).

    python eval/run_explanations.py   (needs GROQ_API_KEY)

Pass when the grounding check passes on the first or second try for >= 9 trips, the rest use the template,
and no ungrounded name or ₹ amount reaches the user. Writes eval/out/explanations.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from api.ai import explain, groq_client, grounding  # noqa: E402
from tripwise import config  # noqa: E402
from tripwise.models import TripRequest, dump  # noqa: E402
from tripwise.variants import plan_variants  # noqa: E402


def main() -> int:
    trips = [t for t in json.loads((ROOT / "eval" / "test_trips.json").read_text(encoding="utf-8")) if t["expect"] == "ok"][:10]
    rows, llm_ok, leaks = [], 0, 0
    for t in trips:
        req = TripRequest.model_validate(t["request"])
        res = dump(plan_variants(req))
        try:
            out = explain.explain(req.model_dump(mode="json", by_alias=True), res["variants"])
        except groq_client.Unavailable:          # Groq refused: wait and try once more
            time.sleep(config.default().groq["eval_retry_wait_s"])
            out = explain.explain(req.model_dump(mode="json", by_alias=True), res["variants"])
        by = {p["variant"]: p for p in res["variants"]}
        bad = {v: grounding.check_plan_text(txt, by[v], req.destination) for v, txt in out["texts"].items()}
        leaks += sum(bool(b) for b in bad.values())
        grounded = all(s != "template" for s in out["source"].values())
        llm_ok += grounded
        rows.append({"id": t["id"], **out, "final_problems": bad})
        print(t["id"], out["source"], "calls", out["calls"])
        time.sleep(config.default().groq["eval_pause_s"])
    (ROOT / "eval" / "out").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval" / "out" / "explanations.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"grounded on first or second try: {llm_ok}/{len(trips)}; ungrounded texts shown: {leaks}")
    return 0 if llm_ok >= 9 and leaks == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
