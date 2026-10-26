"""Chat about a saved plan (AI-FR-03, AI-FR-04, AI-FR-05; FR-031–FR-034, NFR-005).

Call 1: Groq tool calling picks fixed tools. Their arguments are checked and activity names are resolved
against the trip's city; each change tool maps to a 004 replan change set and the engine makes the new
version (Constitution II: the model never writes a plan). Call 2 turns the engine's facts (the version diff,
a near-miss reason or a trial result) into a reply, which must pass the grounding check or is replaced by a
template. At most two Groq calls per message.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import time

from api import solver
from api.ai import diff as diffs, explain, groq_client, grounding
from api.ai.prompts import TOOLS, chat_system, reply_system
from api.errors import ApiError
from api.routers.versions import apply_changes, replan_request
from api.validation import check_trip
from tripwise import config, data
from tripwise.models import Plan, dump
from tripwise.tradeoffs import variant_at

log = logging.getLogger("tripwise.ai")

CHANGE_TOOLS = {"lock_activity", "exclude_activity", "set_budget", "set_day_hours", "set_all_hours", "set_hotel_tier",
                "set_transport", "set_pace", "set_interest", "move_activity", "regenerate"}
NAMED = {"lock_activity", "exclude_activity", "move_activity"}
CLOSEST_HINT = {
    "lock_activity": "keep or add an activity (\"make sure we see Amber Fort\")",
    "exclude_activity": "drop an activity (\"skip the zoo\")",
    "set_budget": "change your budget (\"raise the budget to 50000\")",
    "set_day_hours": "change the hours on one day (\"only 5 hours on day 2\")",
    "set_all_hours": "change your hours out each day",
    "set_hotel_tier": "change the hotel level (budget, mid-range or premium)",
    "set_transport": "change how you travel there or back (train, bus or flight)",
    "set_pace": "change the pace (relaxed, balanced or packed)",
    "set_interest": "change how much an interest counts (\"more food\")",
    "move_activity": "move an activity to another day",
    "explain": "explain why something is or isn't in your plan",
    "none": "change activities, budget, hours, hotel level, transport, pace or interests in this plan",
}
REASON_TEXT = {"budget": "it didn't fit the budget", "time": "there wasn't time for it", "closed": "it is closed on your days"}


class Clarify(Exception):
    """The message needs a clarifying reply instead of a change."""


# --- names -------------------------------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def resolve(name: str, city: str) -> tuple[str, str]:
    """(attraction_id, canonical name), or raises Clarify when the name is unknown or ambiguous."""
    cands = {a.attraction_id: a.name for a in data.default().attractions.values() if a.city_id == city}
    q = re.sub(r"^(the|a|an) ", "", _norm(name or ""))     # "the temple" is as vague as "temple"
    if not q:
        raise Clarify("Which activity do you mean?")
    exact = [i for i, n in cands.items() if _norm(n) == q]
    if len(exact) == 1:
        return exact[0], cands[exact[0]]
    part = [i for i, n in cands.items() if q in _norm(n) or (len(_norm(n)) >= 5 and _norm(n) in q)]
    if len(part) == 1:
        return part[0], cands[part[0]]
    pool = part or list(cands)
    scored = sorted(((difflib.SequenceMatcher(None, q, _norm(cands[i])).ratio(), i) for i in pool), reverse=True)
    cut = config.default().chat["name_match_cutoff"]
    top = [(s, i) for s, i in scored if s >= cut]
    if top and (len(top) == 1 or top[0][0] - top[1][0] >= config.default().chat["name_match_margin"]):
        return top[0][1], cands[top[0][1]]
    options = [cands[i] for _, i in (top or scored)[:3]] if (top or part) else []
    if options:
        raise Clarify("Which one do you mean: " + ", ".join(options[:-1]) + (" or " if len(options) > 1 else "")
                      + options[-1] + "?")
    city_name = data.default().cities[city].name
    raise Clarify(f"I couldn't find \"{name}\" in {city_name}. Try the name as it appears on the plan or the map.")


# --- tool calls → change sets ----------------------------------------------------------------------------

def _calls(msg: dict) -> list[tuple[str, dict]]:
    out = []
    for c in msg.get("tool_calls") or []:
        fn = c.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = None
        if fn.get("name") not in {t["function"]["name"] for t in TOOLS} or not isinstance(args, dict):
            raise Clarify("Sorry, I didn't catch that. Could you say it another way?")
        out.append((fn["name"], args))
    return out


def to_changes(calls: list[tuple[str, dict]], request: dict, city: str) -> dict:
    """One merged replan change set for the change tools (AI-FR-03)."""
    n_days = len(_dates(request))
    locks, excludes = list(request.get("locks", [])), list(request.get("excludes", []))
    pins = dict(request.get("pins") or {})
    ch: dict = {}

    def prefs(k, v):
        ch.setdefault("prefs", {})
        if k in ("interests", "modes"):
            ch["prefs"].setdefault(k, {}).update(v)
        else:
            ch["prefs"][k] = v

    def day(v):
        if not isinstance(v, int) or not 1 <= v <= n_days:
            raise Clarify(f"Your trip has days 1 to {n_days}. Which day do you mean?")
        return v

    for name, a in calls:
        if name in NAMED:
            aid, _ = resolve(a.get("name", ""), city)
        if name == "lock_activity":
            locks = locks + [aid] if aid not in locks else locks
            excludes = [x for x in excludes if x != aid]
            ch |= {"locks": locks, "excludes": excludes}
        elif name == "exclude_activity":
            excludes = excludes + [aid] if aid not in excludes else excludes
            locks = [x for x in locks if x != aid]
            ch |= {"locks": locks, "excludes": excludes}
            if aid in pins:
                ch.setdefault("pins", {})[aid] = None
        elif name == "move_activity":
            ch.setdefault("pins", {})[aid] = day(a.get("day"))
            if aid in excludes:
                excludes = [x for x in excludes if x != aid]
                ch["excludes"] = excludes
        elif name == "set_budget":
            ch["budget_total"] = a.get("budget_total")
        elif name == "set_day_hours":
            ch.setdefault("day_hours", {})[str(day(a.get("day")))] = a.get("hours")
        elif name == "set_all_hours":
            prefs("daily_hours_out", a.get("hours"))
            for d in (request.get("day_hours") or {}):
                ch.setdefault("day_hours", {})[str(d)] = None
        elif name == "set_hotel_tier":
            prefs("comfort", a.get("tier"))
        elif name == "set_pace":
            prefs("pace", a.get("pace"))
        elif name == "set_interest":
            prefs("interests", {a.get("interest"): a.get("weight")})
        elif name == "set_transport":
            mode = a.get("mode")
            cls = a.get("class") or config.default().chat["default_class"].get(mode)
            if (mode, cls) not in data.default().fares:
                raise Clarify(f"There is no {cls} class for {mode}. Which class do you want?")
            j = {"mode": mode, "class": cls}
            dirs = ["out", "ret"] if a.get("direction") == "both" else [a.get("direction")]
            if any(d not in ("out", "ret") for d in dirs):
                raise Clarify("The way there, the way back, or both?")
            ch.setdefault("transport", {}).update({d: j for d in dirs})
        elif name == "regenerate":
            ch.setdefault("locks", locks)          # a no-op change: plan again from the current settings
    return ch


def _dates(request: dict) -> list:
    from datetime import date, timedelta
    s, e = date.fromisoformat(str(request["start_date"])), date.fromisoformat(str(request["end_date"]))
    return [s + timedelta(days=i) for i in range((e - s).days + 1)]


# --- context and replies -------------------------------------------------------------------------------------

def context(trip: dict, plan: dict, request: dict) -> dict:
    ds = data.default()
    name = lambda i: ds.attractions[i].name if i in ds.attractions else i   # noqa: E731
    return {
        "city": ds.cities[request["destination"]].name, "from": ds.cities[request["origin"]].name,
        "dates": [str(request["start_date"]), str(request["end_date"])], "people": request["people"],
        "budget_total": request["budget_total"], "plan_total": plan["budget"]["total"],
        "prefs": request["prefs"], "variant": trip["selected_variant"],
        "hotel": {"name": plan["hotel"]["name"], "tier": plan["hotel"]["tier"]},
        "transport": {k: f"{plan['transport'][k]['mode']} {plan['transport'][k]['class']}" for k in ("outbound", "return")},
        "days": [{"day": d["day"], "date": d["date"], "activities": [s["name"] for s in d["stops"]]} for d in plan["days"]],
        "near_misses": [{"name": m["name"], "reason": m["reason"]} for m in plan["near_misses"]],
        "kept_in": [name(i) for i in request.get("locks", [])], "kept_out": [name(i) for i in request.get("excludes", [])],
        "moved": {name(i): d for i, d in (request.get("pins") or {}).items()},
        "day_hours": request.get("day_hours") or {},
    }


def _reply(facts: dict, fallback: str, city: str, names: set[str], amounts: set[int], deadline: float) -> tuple[str, str]:
    """Call 2, grounded, or the template (text, source). Call 2 gets the time left before the message deadline
    minus 0.5 s, and is skipped when under 1 s is left (AI-FR-03)."""
    left = deadline - time.perf_counter() - 0.5
    if left < 1:
        log.info("chat reply: %.1f s left before the deadline, template used", left + 0.5)
        return fallback, "template"
    try:
        msg = groq_client.chat([{"role": "system", "content": reply_system()},
                                {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}],
                               temperature=config.default().groq["temperature_explain"], timeout=left,
                               deadline=time.perf_counter() + left)
    except groq_client.Unavailable:
        return fallback, "template"
    text = (msg.get("content") or "").strip()
    if text and not grounding.problems(text, city, names, amounts):
        return text, "llm"
    return fallback, "template"


def _money(v: int) -> str:
    return f"₹{abs(v):,}"


def change_template(version: int, d: dict) -> str:
    parts = []
    if d["added"]:
        parts.append("added " + ", ".join(d["added"]))
    if d["removed"]:
        parts.append("removed " + ", ".join(d["removed"]))
    for m in d["moved"]:
        parts.append(f"moved {m['name']} to day {m['to_day']}")
    if d["hotel"]:
        parts.append(f"changed the hotel to {d['hotel']['to']}")
    for k, t in d["transport"].items():
        parts.append(f"changed the {'outbound' if k == 'outbound' else 'return'} journey to {t['to']}")
    head = f"Done, this is version {version}. " + ("I " + "; ".join(parts) + ". " if parts else "The plan came out the same. ")
    if d["delta_cost"]:
        head += (f"The estimated total is now {_money(d['new_total'])} "
                 f"({'up' if d['delta_cost'] > 0 else 'down'} {_money(d['delta_cost'])}).")
    return head.strip()


# --- the message handler -------------------------------------------------------------------------------------

async def handle(trip: dict, base: dict, user: dict, message: str, history: list[dict]) -> dict:
    """Returns {"text", "actions", "version"} (version is the new full version or None)."""
    t0 = time.perf_counter()
    deadline = t0 + config.default().chat["deadline_s"]
    request, plan = base["request"], base["plan"]
    city = request["destination"]
    messages = [{"role": "system", "content": chat_system(context(trip, plan, request))}]
    messages += [{"role": m["role"], "content": m["text"]} for m in history[-config.default().chat["history_messages"]:]]
    messages.append({"role": "user", "content": message})
    g = config.default().groq
    try:
        msg = await solver.run_blocking(groq_client.chat, messages, temperature=g["temperature_tools"],
                                        tools=TOOLS, tool_choice="required", timeout=g["timeout_tools_s"],
                                        deadline=time.perf_counter() + g["timeout_tools_s"])
    except groq_client.Unavailable:
        return {"text": "The assistant is unavailable right now, so nothing was changed. You can still edit the plan "
                        "with the form.", "actions": {"kind": "unavailable"}, "version": None}
    try:
        calls = _calls(msg)
        if not calls:
            raise Clarify("Sorry, I didn't catch that. Could you say it another way?")
        tools = [{"name": n, "args": a} for n, a in calls]
        names = [n for n, _ in calls]
        if any(n in CHANGE_TOOLS for n in names):
            changes = to_changes([c for c in calls if c[0] in CHANGE_TOOLS], request, city)
            return await _change(trip, base, user, message, changes, tools, deadline)
        if "explain" in names:
            return await _why(trip, base, dict(calls)["explain"].get("name"), tools, deadline)
        closest = dict(calls).get("unsupported", {}).get("closest", "none")
        text = ("Sorry, that's outside what I can do here: I can't book, check weather or plan other cities. I can "
                + CLOSEST_HINT.get(closest, CLOSEST_HINT["none"]) + ".")
        return {"text": text, "actions": {"kind": "unsupported", "tools": tools}, "version": None}
    except Clarify as c:
        return {"text": str(c), "actions": {"kind": "clarify", "tools": [{"name": n, "args": a} for n, a in _safe_calls(msg)]},
                "version": None}


def _safe_calls(msg: dict) -> list:
    try:
        return _calls(msg)
    except Clarify:
        return []


async def _change(trip: dict, base: dict, user: dict, message: str, changes: dict, tools: list, deadline: float) -> dict:
    city = base["request"]["destination"]
    try:
        v = await replan_request(str(trip["id"]), user, changes, "chat", message[:200])
    except ApiError as e:
        if e.status == 409 and e.code == "infeasible":
            text = f"I couldn't make that change: {e.message} Your plan is unchanged."
            return {"text": text, "actions": {"kind": "infeasible", "tools": tools, "changes": changes}, "version": None}
        if e.status == 422:
            return {"text": f"That change isn't possible: {e.message}", "actions": {"kind": "clarify", "tools": tools},
                    "version": None}
        raise
    d = diffs.diff(base["plan"], v["plan"])
    facts = {"request": message, "new_version": v["version"], "budget_total": v["request"]["budget_total"],
             "changes": d}
    names = grounding.plan_names(base["plan"]) | grounding.plan_names(v["plan"])
    amounts = (grounding.numbers(base["plan"]) | grounding.numbers(v["plan"]) | diffs.amounts(d)
               | {v["request"]["budget_total"]})
    text, src = await solver.run_blocking(_reply, facts, change_template(v["version"], d), city, names, amounts, deadline)
    return {"text": text, "actions": {"kind": "change", "tools": tools, "changes": changes, "diff": d, "reply": src},
            "version": v}


async def _why(trip: dict, base: dict, name: str | None, tools: list, deadline: float) -> dict:
    request, plan = base["request"], base["plan"]
    city = request["destination"]
    names, amounts = grounding.plan_names(plan), grounding.numbers(plan)
    if not name:
        facts = {"question": "about the plan", "plan": explain.compact(plan)}
        text, src = await solver.run_blocking(_reply, facts, explain.template(plan), city, names, amounts, deadline)
        return {"text": text, "actions": {"kind": "why", "tools": tools, "reply": src}, "version": None}
    aid, canon = resolve(name, city)
    a = data.default().attractions[aid]
    where = [d["day"] for d in plan["days"] for s in d["stops"] if s["attraction_id"] == aid]
    miss = next((m for m in plan["near_misses"] if m["attraction_id"] == aid), None)
    fee = a.fee * request["people"]
    facts: dict = {"activity": canon, "entry_fee_for_group": fee, "visit_minutes": a.visit}
    amounts |= {fee}
    names |= {canon}
    if where:
        facts["status"] = f"in the plan on day {where[0]}"
        fallback = f"{canon} is already in your plan, on day {where[0]}."
    elif aid in request.get("excludes", []):
        facts["status"] = "kept out at the traveller's request"
        fallback = f"You asked to keep {canon} out. Say \"add {canon}\" to bring it back."
    elif miss:
        facts |= {"status": "near-miss", "reason": REASON_TEXT[miss["reason"]]}
        fallback = (f"{canon} nearly made it, but {REASON_TEXT[miss['reason']]}. Entry for your group is about "
                    f"{_money(fee)} and a visit takes about {a.visit} minutes.")
    else:                                          # a trial engine call with it locked; nothing is saved
        req = check_trip(apply_changes(request, {"locks": list(request.get("locks", [])) + [aid]}))
        res = await solver.solve(variant_at, req, trip["selected_variant"])
        if isinstance(res, Plan):
            p = dump(res)
            d = diffs.diff(plan, p)
            facts |= {"status": "not in the plan, but it would fit if kept in", "trial_changes": d}
            names |= grounding.plan_names(p)
            amounts |= grounding.numbers(p) | diffs.amounts(d)
            fallback = (f"{canon} scored a little lower than what's in your plan. It would fit if you keep it in: the total "
                        f"would be {_money(p['budget']['total'])}"
                        + (f" and {', '.join(d['removed'])} would drop out." if d["removed"] else "."))
        else:
            out = dump(res)
            facts |= {"status": "would not fit even if kept in", "engine_message": out.get("message")}
            fallback = f"{canon} wouldn't fit even if you keep it in: {out.get('message', '')}".strip()
    text, src = await solver.run_blocking(_reply, facts, fallback, city, names, amounts, deadline)
    return {"text": text, "actions": {"kind": "why", "tools": tools, "facts": facts, "reply": src}, "version": None}
