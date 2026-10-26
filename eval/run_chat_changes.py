"""AI-AT-04: 10 chat changes end to end (real Groq, the API in-process on schema app_test).

    python eval/run_chat_changes.py   (needs GROQ_API_KEY, DATABASE_URL, JWT_SECRET)

Pass when each message creates a new version that passes the validator, and the diff the reply was written from
equals the diff between the stored versions. The same run gives AI-AT-07 (chat p95 <= 8 s; the pauses between
messages are not timed). Writes eval/out/chat_changes.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

os.environ["DB_SCHEMA"] = "app_test"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from api.ai import diff as diffs  # noqa: E402
from api.main import app  # noqa: E402
from api.validation import today  # noqa: E402
from tripwise import config, data  # noqa: E402
from tripwise.models import Plan, TripRequest  # noqa: E402
from validator.validate import validate  # noqa: E402

MESSAGES = [
    "Make sure we visit Nahargarh Fort",
    "Drop Jal Mahal please",
    "Increase our budget to 60000",
    "We only want 6 hours out on day 2",
    "Switch to a budget hotel",
    "Make the trip more relaxed",
    "We love food, bump that up to 5",
    "Put Hawa Mahal on day 3",
    "Come back by train in 3A",
    "Let's be out 10 hours every day",
]


def main() -> int:
    from datetime import timedelta
    start = today() + timedelta(days=40)
    body = {"origin": "DEL", "destination": "JAI", "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=2)).isoformat(), "people": 2, "budget_total": 50000,
            "prefs": {"daily_hours_out": 9, "pace": "balanced", "comfort": "mid", "avoid_crowds": False,
                      "modes": {"train": "neutral", "bus": "neutral", "flight": "neutral"},
                      "interests": {"nature": 1, "adventure": 0, "food": 2, "history": 5, "culture": 4, "spiritual": 1,
                                    "shopping": 1, "relaxation": 1, "nightlife": 0}}}
    rows, ok = [], 0
    with TestClient(app) as c:
        r = c.post("/auth/signup", json={"email": f"eval-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 1"})
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        t = c.post("/trips", headers=h, json=body).json()
        tid = t["id"]
        c.post(f"/trips/{tid}/select", headers=h, json={"variant": "balanced"})
        for m in MESSAGES:
            t0 = time.perf_counter()
            out = c.post(f"/trips/{tid}/chat", headers=h, json={"message": m}).json()
            secs = time.perf_counter() - t0
            a, v = out["assistant"], out["version"]
            problems = []
            if v is None:
                problems.append(f"no new version ({a['actions'].get('kind')})")
            else:
                errs = validate(Plan.model_validate(v["plan"]), TripRequest.model_validate(v["request"]), data.default(),
                                config.default().as_dict())
                problems += [f"validator: {e}" for e in errs]
                prev = c.get(f"/trips/{tid}/versions/{v['version'] - 1}", headers=h).json()
                if a["actions"]["diff"] != diffs.diff(prev["plan"], v["plan"]):
                    problems.append("reply diff differs from the version diff")
            ok += not problems
            rows.append({"message": m, "reply": a["text"], "tools": a["actions"].get("tools"),
                         "reply_source": a["actions"].get("reply"), "version": a["version"], "seconds": round(secs, 2),
                         "problems": problems})
            print(f"{'OK ' if not problems else 'BAD'} {secs:4.1f}s  {m}\n     {a['text']}" + (f"\n     {problems}" if problems else ""))
            time.sleep(15)        # Groq free tier: stay under the tokens-per-minute limit
    (ROOT / "eval" / "out").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval" / "out" / "chat_changes.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"changes with a valid new version and matching diff: {ok}/{len(MESSAGES)}")
    times = sorted(r["seconds"] for r in rows)
    p95 = times[min(len(times) - 1, int(0.95 * len(times)))]
    print(f"AI-AT-07 chat timing over {len(times)} messages: p95 {p95:.1f} s, max {times[-1]:.1f} s (limit 8 s)")
    return 0 if ok == len(MESSAGES) and p95 <= 8 else 1


if __name__ == "__main__":
    sys.exit(main())
