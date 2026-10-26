"""008 T05 / DEP-AT-02: live timings on the deployed API (DEP-FR-03).

    python eval/run_live.py [--api URL] [--part trips|chat]   (chat uses real Groq on the VM; about 4 min)

Signs up one new live-check-…@example.com user, then times from this machine (so network time is included):
  - POST /trips for test trips T01–T10 (all variants; NFR-001 p95 <= 5 s),
  - 10 chat changes on one Delhi to Jaipur trip, the AI-AT-04 messages (NFR-002 p95 <= 8 s; the pauses between
    messages are not timed).
--part runs one half and keeps the other half's saved rows. Writes eval/out/live.json; eval/LIVE.md records the result.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]

# the AI-AT-04 messages (eval/run_chat_changes.py; not imported, since that module loads the API in-process)
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
API = "https://lekhya-audiobook.centralindia.cloudapp.azure.com/tripwise"
ORIGIN = "https://tripwise-inky.vercel.app"


def p95(xs: list[float]) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(0.95 * len(s)))]


def main() -> int:
    api = sys.argv[sys.argv.index("--api") + 1] if "--api" in sys.argv else API
    trips = json.loads((ROOT / "eval" / "test_trips.json").read_text(encoding="utf-8"))[:10]
    c = httpx.Client(base_url=api, timeout=60, headers={"Origin": ORIGIN})
    r = c.post("/auth/signup", json={"email": f"live-check-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 1"})
    r.raise_for_status()
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    part = sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else "both"
    out_file = ROOT / "eval" / "out" / "live.json"
    out = json.loads(out_file.read_text(encoding="utf-8")) if part != "both" and out_file.exists() else {"trips": [], "chat": []}
    out["api"] = api
    if part in ("both", "trips"):
        out["trips"], out["trips_date"] = [], date.today().isoformat()
    for t in trips if part in ("both", "trips") else []:
        t0 = time.perf_counter()
        r = c.post("/trips", json=t["request"])
        secs = time.perf_counter() - t0
        res = r.json().get("result") or {}
        out["trips"].append({"id": t["id"], "http": r.status_code, "status": res.get("status"), "seconds": round(secs, 2)})
        print(f"{t['id']} HTTP {r.status_code} {res.get('status')} {secs:.2f} s", flush=True)
    if part in ("both", "chat"):
        out["chat"], out["chat_date"] = chat(c), date.today().isoformat()
    tt, ct = [x["seconds"] for x in out["trips"]], [x["seconds"] for x in out["chat"]]
    out["summary"] = {"trips_p95": tt and p95(tt), "trips_max": tt and max(tt), "chat_p95": ct and p95(ct), "chat_max": ct and max(ct)}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"variants p95 {out['summary']['trips_p95']} s over {len(tt)} trips (limit 5 s); "
          f"chat p95 {out['summary']['chat_p95']} s over {len(ct)} messages (limit 8 s)")
    return 0 if len(tt) == 10 and len(ct) == 10 and p95(tt) <= 5 and p95(ct) <= 8 else 1


def chat(c: httpx.Client) -> list[dict]:
    rows = []
    start = date.today() + timedelta(days=40)
    body = {"origin": "DEL", "destination": "JAI", "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=2)).isoformat(), "people": 2, "budget_total": 50000,
            "prefs": {"daily_hours_out": 9, "pace": "balanced", "comfort": "mid", "avoid_crowds": False,
                      "modes": {"train": "neutral", "bus": "neutral", "flight": "neutral"},
                      "interests": {"nature": 1, "adventure": 0, "food": 2, "history": 5, "culture": 4, "spiritual": 1,
                                    "shopping": 1, "relaxation": 1, "nightlife": 0}}}
    tid = c.post("/trips", json=body).json()["id"]
    c.post(f"/trips/{tid}/select", json={"variant": "balanced"}).raise_for_status()
    for m in MESSAGES:
        t0 = time.perf_counter()
        r = c.post(f"/trips/{tid}/chat", json={"message": m})
        secs = time.perf_counter() - t0
        a = r.json().get("assistant") or {}
        v = r.json().get("version")
        rows.append({"message": m, "http": r.status_code, "version": v and v["version"],
                     "reply_source": (a.get("actions") or {}).get("reply"), "seconds": round(secs, 2)})
        print(f"HTTP {r.status_code} v{v and v['version']} {secs:.2f} s  {m}", flush=True)
        time.sleep(15)        # Groq free tier: stay under the tokens-per-minute limit
    return rows


if __name__ == "__main__":
    sys.exit(main())
