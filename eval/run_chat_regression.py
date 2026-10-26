"""Chat regression cases from real owner failures (eval/chat_regression.json), separate from AI-AT-03.

    python eval/run_chat_regression.py [--runs N]   (needs GROQ_API_KEY; default 3 runs per case)

Each case is a real message and the request it was sent against. The message goes through the same steps as the
chat endpoint: call 1 (real Groq, real system prompt, tools and context), name resolution and the change mapping
(limit_kind expansion included), the no-change check, the engine re-plan, and call 2 or the fixed replies. A run
passes when the new plan meets the case's expectation, counted by the attractions' kind (001 §5.5). The reply is
printed for review. Writes eval/out/chat_regression.json.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from api.ai import chat, diff as diffs, grounding, groq_client  # noqa: E402
from api.ai.prompts import TOOLS, chat_system  # noqa: E402
from api.routers.versions import apply_changes  # noqa: E402
from api.validation import check_trip  # noqa: E402
from tripwise import config, data  # noqa: E402
from tripwise.models import Plan, TripRequest, dump  # noqa: E402
from tripwise.tradeoffs import variant_at  # noqa: E402


def kinds(plan: dict, wanted) -> dict:
    ds = data.default()
    stops = [ds.attractions[s["attraction_id"]].kind for d in plan["days"] for s in d["stops"]]
    return {k: stops.count(k) for k in wanted}


def run(case: dict) -> dict:
    g = config.default().groq
    req = TripRequest.model_validate(case["request"])
    request = req.model_dump(mode="json", by_alias=True)
    city = request["destination"]
    plan = dump(variant_at(req, case["variant"]))
    want = list(case["expect"])
    out = {"tools": [], "before": kinds(plan, want)}
    messages = [{"role": "system", "content": chat_system(chat.context({"selected_variant": case["variant"]}, plan, request))},
                {"role": "user", "content": case["message"]}]
    t0 = time.perf_counter()
    secs = lambda: round(time.perf_counter() - t0, 2)   # noqa: E731
    try:
        msg = groq_client.chat(messages, temperature=g["temperature_tools"], tools=TOOLS, tool_choice="required",
                               timeout=g["timeout_tools_s"])
    except groq_client.Unavailable as exc:      # as the endpoint: "assistant unavailable", a failed run
        return out | {"ok": False, "outcome": f"unavailable ({exc})", "seconds": secs()}
    calls = chat._calls(msg)
    tools = [{"name": n, "args": a} for n, a in calls]
    out["tools"] = tools
    names = [n for n, _ in calls]
    try:
        if not any(n in chat.CHANGE_TOOLS for n in names):
            raise chat.Clarify(f"no change tool ({names})")
        changes = chat.to_changes([c for c in calls if c[0] in chat.CHANGE_TOOLS], request, city, plan)
        if not chat.applied(request, changes) and "regenerate" not in names:
            raise chat.NoChange("nothing to apply")
    except (chat.Clarify, chat.NoChange) as c:
        return out | {"ok": False, "outcome": f"{type(c).__name__}: {c}", "seconds": secs()}
    res = variant_at(check_trip(apply_changes(request, changes)), case["variant"])
    if not isinstance(res, Plan):
        return out | {"ok": False, "outcome": "infeasible", "seconds": secs()}
    new = dump(res)
    nreq = res and check_trip(apply_changes(request, changes)).model_dump(mode="json", by_alias=True)
    after = kinds(new, want)
    ok = all(after[k] <= lim["max"] for k, lim in case["expect"].items())
    d = diffs.diff(plan, new)
    if chat.empty(d):
        return out | {"ok": ok, "outcome": "plan unchanged", "after": after, "reply_source": "no_change", "seconds": secs()}
    facts = chat.reply_facts(2, nreq, d, changes, request, tools)
    known = grounding.plan_names(plan) | grounding.plan_names(new) | chat.change_names(changes)
    amounts = grounding.numbers(plan) | grounding.numbers(new) | diffs.amounts(d) | {nreq["budget_total"]}
    text, src = chat._reply(facts, chat.change_template(2, d), city, known, amounts,
                            time.perf_counter() + config.default().chat["deadline_s"])
    covered = set(d["added"]) | set(d["removed"]) | {m["name"] for m in d["moved"]} | chat.change_names(changes)
    missed = chat.unchanged_named(case["message"], city, covered)
    if missed:
        text += f" I didn't change {', '.join(missed)}; ask again naming {'it' if len(missed) == 1 else 'them'} if you want."
    return out | {"ok": ok, "outcome": "plan", "after": after, "reply": text, "reply_source": src, "seconds": secs()}


def main() -> int:
    cases = json.loads((ROOT / "eval" / "chat_regression.json").read_text(encoding="utf-8"))
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 3
    rows, passed = [], 0
    for c in cases:
        for i in range(runs):
            r = run(c)
            rows.append({"id": c["id"], "run": i + 1, **r})
            passed += r["ok"]
            print(f"{'OK ' if r['ok'] else 'BAD'} {c['id']} run {i + 1}: {r['outcome']} {r['before']} -> {r.get('after')}")
            print(f"     tools: {json.dumps(r['tools'], ensure_ascii=False)}")
            if r.get("reply"):
                print(f"     reply ({r['reply_source']}): {r['reply']}")
            time.sleep(config.default().groq["eval_pause_s"])
    (ROOT / "eval" / "out").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval" / "out" / "chat_regression.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"regression: {passed}/{len(rows)} runs meet the request")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
