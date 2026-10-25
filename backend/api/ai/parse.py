"""Free-text preferences → the 002 prefs schema (AI-FR-01; FR-006).

One Groq call in JSON mode. The output is validated (the same rules as the form); invalid output gets one
retry with the errors, then the caller tells the user to use the sliders. Trip fields (cities, dates, people,
budget) are returned only when the text states them.
"""

from __future__ import annotations

import json
from datetime import date

from api.ai import groq_client
from api.validation import DEFAULT_PREFS, MODES, check_prefs, today
from tripwise import config, data
from tripwise.models import TAGS


class Unparseable(Exception):
    """The model's answer failed validation twice."""


def system_prompt() -> str:
    cities = ", ".join(f"{c.city_id} = {c.name}" for c in data.default().cities.values())
    return f"""You turn a traveller's description of a trip in India into structured preferences for a planner.
Reply with one JSON object only, with these keys:
- "prefs": {{
    "daily_hours_out": number 4-14 (hours per day out of the hotel; 9 if not said),
    "interests": {{{", ".join(f'"{t}"' for t in TAGS)}: whole numbers 0-5 (0 = not interested, 5 = loves it);
                  at least one above 0; infer from what they mention and give 0-1 to what they dislike}},
    "pace": "relaxed" | "balanced" | "packed",
    "comfort": "budget" | "mid" | "premium" (the hotel level),
    "modes": {{"train", "bus", "flight": each "preferred" | "neutral" | "avoid"}},
    "avoid_crowds": true | false }}
- optional, only if the text clearly states them: "origin" and "destination" (city codes from this list only:
  {cities}; a single city named as the place to visit is the destination, and "from X" is the origin), "start_date" and "end_date" (YYYY-MM-DD; today is {today().isoformat()}), "people" (1-6),
  and either "budget_total" or "budget_per_person" (whole rupees; "1.5 lakh" = 150000, "20k" = 20000).
Never invent values the text does not support; use the defaults above. Do not add other keys."""


def _validate(obj) -> tuple[dict, dict]:
    """(clean result, field errors)."""
    errs: dict = {}
    if not isinstance(obj, dict):
        return {}, {"body": "Reply must be a JSON object."}
    out: dict = {"prefs": check_prefs(obj.get("prefs") or {}, errs)}
    ds = data.default()
    a = config.default().api
    for k in ("origin", "destination"):
        v = obj.get(k)
        if v is None:
            continue
        if v not in ds.cities:
            errs[k] = f"Unknown city code {v!r}."
        else:
            out[k] = v
    if out.get("origin") and out.get("origin") == out.get("destination"):
        errs["destination"] = "Destination must differ from origin."
    for k in ("start_date", "end_date"):
        v = obj.get(k)
        if v is None:
            continue
        try:
            d = date.fromisoformat(v)
            out[k] = d.isoformat()
        except (TypeError, ValueError):
            errs[k] = "Use YYYY-MM-DD."
    if "people" in obj and obj["people"] is not None:
        p = obj["people"]
        if isinstance(p, int) and not isinstance(p, bool) and a["people"][0] <= p <= a["people"][1]:
            out["people"] = p
        else:
            errs["people"] = "1 to 6 people."
    for k in ("budget_total", "budget_per_person"):
        v = obj.get(k)
        if v is None:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            out[k] = int(round(v))
        else:
            errs[k] = "Whole rupees."
    if "budget_total" in out and "budget_per_person" in out:
        out.pop("budget_per_person")
    extra = set(obj) - {"prefs", "origin", "destination", "start_date", "end_date", "people", "budget_total",
                        "budget_per_person"}
    if extra:
        errs["body"] = f"Unexpected keys: {', '.join(sorted(extra))}."
    return out, errs


def parse(text: str) -> dict:
    """Raises groq_client.Unavailable or Unparseable."""
    t = config.default().groq["temperature_parse"]
    messages = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": text}]
    for attempt in range(2):
        msg = groq_client.chat(messages, temperature=t, json_mode=True)
        content = msg.get("content") or ""
        try:
            obj = json.loads(content)
        except json.JSONDecodeError:
            obj, errs = None, {"body": "Not valid JSON."}
        else:
            out, errs = _validate(obj)
            if not errs:
                return out
        if attempt == 0:
            messages += [{"role": "assistant", "content": content},
                         {"role": "user", "content": f"That reply is not valid: {json.dumps(errs)}. Reply again with a corrected JSON object."}]
    raise Unparseable(errs)


def defaults() -> dict:
    return {"prefs": DEFAULT_PREFS | {"modes": {m: "neutral" for m in MODES}}}
