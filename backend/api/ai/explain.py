"""Variant explanations (AI-FR-02; FR-030, NFR-005).

One Groq call explains every variant of a trip. The model sees only the plans (compacted), their near-misses
and the user's prefs. Each text is grounding-checked; failing variants are regenerated once, then replaced by
a template built from the plan, so no ungrounded name or ₹ amount reaches the user.
"""

from __future__ import annotations

import json

from api.ai import groq_client, grounding
from api.ai.prompts import explain_system
from tripwise import config

VARIANT_LABEL = {"experience": "Experience", "balanced": "Balanced", "saver": "Saver"}


def compact(plan: dict) -> dict:
    t, b = plan["transport"], plan["budget"]
    return {
        "total_cost": b["total"], "budget_total": b["budget_total"],
        "costs": {k: b[k] for k in ("outbound", "return", "stay", "food", "entry_fees", "local_travel", "contingency")},
        "transport": {k: {"mode": j["mode"], "class": j["class"], "hours": round(j["minutes"] / 60, 1),
                          "overnight": j["overnight"], "cost": j["cost"]} for k, j in (("outbound", t["outbound"]), ("return", t["return"]))},
        "hotel": {"name": plan["hotel"]["name"], "tier": plan["hotel"]["tier"], "nights": plan["hotel"]["nights"],
                  "cost": plan["hotel"]["cost"]},
        "days": [{"day": d["day"], "date": d["date"],
                  "activities": [{"name": s["name"], "entry_cost": s["entry_cost"]} for s in d["stops"]]} for d in plan["days"]],
        "near_misses": [{"name": m["name"], "reason": m["reason"]} for m in plan["near_misses"]],
    }


def _money(v: int) -> str:
    return f"₹{v:,}"


def template(plan: dict) -> str:
    """A plain explanation built only from the plan (the fallback)."""
    stops = [s["name"] for d in plan["days"] for s in d["stops"]]
    t, h, b = plan["transport"], plan["hotel"], plan["budget"]
    label = VARIANT_LABEL.get(plan.get("variant") or "", "This plan")
    first = (f"{label} fits {len(stops)} activities into {len(plan['days'])} days"
             + (f", including {', '.join(stops[:3])}." if stops else "."))
    travel = (f"You go by {t['outbound']['mode']} ({t['outbound']['class']}) and return by {t['return']['mode']} "
              f"({t['return']['class']}), staying at {h['name']} ({h['tier']}).")
    cost = f"It costs an estimated {_money(b['total'])} of your {_money(b['budget_total'])} budget."
    out = [first, travel, cost]
    if plan["near_misses"]:
        reasons = {"budget": "budget", "time": "time", "closed": "closing days"}
        miss = plan["near_misses"][:2]
        out.append("Left out: " + "; ".join(f"{m['name']} ({reasons[m['reason']]})" for m in miss) + ".")
    return " ".join(out)


def _ask(prefs: dict, plans: dict[str, dict], feedback: dict[str, list[str]] | None = None) -> dict:
    payload = {"preferences": prefs, "variants": {v: compact(p) for v, p in plans.items()}}
    messages = [{"role": "system", "content": explain_system()},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    if feedback:
        messages.append({"role": "user", "content": "Your previous texts had problems; fix them: "
                         + json.dumps(feedback, ensure_ascii=False)})
    msg = groq_client.chat(messages, temperature=config.default().groq["temperature_explain"], json_mode=True)
    try:
        obj = json.loads(msg.get("content") or "")
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _problems(text, plan: dict, city: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return ["missing explanation"]
    return grounding.check_plan_text(text, plan, city)


def explain(request: dict, plans: list[dict]) -> dict:
    """{"texts": {variant: text}, "source": {variant: "llm" | "llm_retry" | "template"}, "calls": n}.

    Raises groq_client.Unavailable if the first call fails (the caller omits explanations with a notice).
    """
    city = request["destination"]
    by_name = {p["variant"]: p for p in plans}
    texts, source, calls = {}, {}, 1
    first = _ask(request["prefs"], by_name)
    failing: dict[str, list[str]] = {}
    for v, p in by_name.items():
        bad = _problems(first.get(v), p, city)
        if bad:
            failing[v] = bad
        else:
            texts[v], source[v] = first[v].strip(), "llm"
    if failing:
        calls = 2
        try:
            second = _ask(request["prefs"], {v: by_name[v] for v in failing}, failing)
        except groq_client.Unavailable:
            second = {}
        for v in failing:
            if not _problems(second.get(v), by_name[v], city):
                texts[v], source[v] = second[v].strip(), "llm_retry"
            else:
                texts[v], source[v] = template(by_name[v]), "template"
    return {"texts": texts, "source": source, "calls": calls}
