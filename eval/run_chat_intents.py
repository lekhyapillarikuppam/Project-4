"""AI-AT-03 / EVAL-FR-03: chat tool accuracy on eval/chat_intents.json (50 messages).

    python eval/run_chat_intents.py [--resume] [--max N]   (needs GROQ_API_KEY; about 30 min on the Groq free tier;
                                                            --max N stops after N new cases, for short batches)

Each message goes through chat call 1 only (Groq tool calling with the real system prompt and trip context; no
replan). A message is correct when the model calls exactly the expected tool with the expected arguments (names
are compared after the server's name resolution). For the 5 ambiguous messages, correct means the server ends
with a clarifying question. Pass: accuracy >= 90%. Writes eval/out/chat_intents.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from api.ai import chat, groq_client  # noqa: E402
from api.ai.prompts import TOOLS, chat_system  # noqa: E402
from tripwise import config  # noqa: E402
from tripwise.models import TripRequest, dump  # noqa: E402
from tripwise.tradeoffs import variant_at  # noqa: E402

REQUEST = {"origin": "DEL", "destination": "JAI", "start_date": "2026-12-14", "end_date": "2026-12-16", "people": 2,
           "budget_total": 50000,
           "prefs": {"daily_hours_out": 9, "pace": "balanced", "comfort": "mid", "avoid_crowds": False, "modes": {},
                     "interests": {"nature": 1, "adventure": 0, "food": 2, "history": 5, "culture": 4, "spiritual": 1,
                                   "shopping": 1, "relaxation": 1, "nightlife": 0}},
           "locks": [], "excludes": []}


def call(messages: list[dict]) -> dict:
    # Groq free tier: 8000 tokens a minute and 200000 a day (rolling). On a refusal, wait 5 min and try again,
    # for up to 3 hours, so a run that meets the daily limit finishes once tokens free up.
    for attempt in range(37):
        try:
            return groq_client.chat(messages, temperature=config.default().groq["temperature_tools"], tools=TOOLS,
                                    tool_choice="required")
        except groq_client.Unavailable as exc:
            if attempt == 36:
                raise
            print(f"   Groq refused ({exc}); waiting 5 min", flush=True)
            time.sleep(300)
    raise AssertionError


def score(case: dict, msg: dict, request: dict) -> tuple[bool, str]:
    try:
        calls = chat._calls(msg)
    except chat.Clarify:
        return False, "malformed tool call"
    names = [n for n, _ in calls]
    if case["outcome"] == "clarify":
        try:
            chat.to_changes([c for c in calls if c[0] in chat.CHANGE_TOOLS], request, "JAI")
            for n, a in calls:
                if n == "explain" and a.get("name"):
                    chat.resolve(a["name"], "JAI")
        except chat.Clarify as c:
            return True, f"clarify: {c}"
        return False, f"no clarifying question ({names})"
    if names != [case["tool"]]:
        return False, f"tools {names}"
    args = calls[0][1]
    for k, v in case["args"].items():
        if k == "attraction":
            try:
                got = chat.resolve(args.get("name", ""), "JAI")[0]
            except chat.Clarify as c:
                return False, f"name {args.get('name')!r}: {c}"
            if got != v:
                return False, f"name {args.get('name')!r} -> {got}"
        elif args.get(k) != v:
            return False, f"{k} {args.get(k)!r} != {v!r}"
    if case["tool"] == "explain" and "attraction" not in case["args"] and args.get("name"):
        try:                       # a general question answered about one activity is still fine if it resolves
            chat.resolve(args["name"], "JAI")
        except chat.Clarify:
            return False, "explain named an unknown activity"
    return True, json.dumps(args, ensure_ascii=False)


def main() -> int:
    cases = json.loads((ROOT / "eval" / "chat_intents.json").read_text(encoding="utf-8"))
    req = TripRequest.model_validate(REQUEST)
    plan = dump(variant_at(req, "balanced"))
    request = req.model_dump(mode="json", by_alias=True)
    system = chat_system(chat.context({"selected_variant": "balanced"}, plan, request))
    out_file = ROOT / "eval" / "out" / "chat_intents.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fresh = "--resume" not in sys.argv
    done = {} if fresh or not out_file.exists() else {r["id"]: r for r in json.loads(out_file.read_text(encoding="utf-8"))}
    batch = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else len(cases)
    rows = []
    for c in cases:
        if c["id"] in done and done[c["id"]]["text"] == c["text"]:
            rows.append(done[c["id"]])
            continue
        if batch == 0:
            print(f"batch done: {len(rows)}/{len(cases)} cases have results; run again with --resume")
            return 2
        batch -= 1
        t0 = time.perf_counter()
        msg = call([{"role": "system", "content": system}, {"role": "user", "content": c["text"]}])
        ok, note = score(c, msg, request)
        rows.append({**c, "ok": ok, "note": note, "seconds": round(time.perf_counter() - t0, 2)})
        out_file.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")   # resumable
        print(f"{'OK ' if ok else 'BAD'} {c['id']} {c['text']!r}: {note}", flush=True)
        time.sleep(30)
    right = sum(r["ok"] for r in rows)
    print(f"tool accuracy {right}/{len(cases)} = {right / len(cases):.0%}")
    return 0 if right / len(cases) >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
