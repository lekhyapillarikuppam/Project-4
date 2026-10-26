"""System prompts and tool schemas for the three Groq uses (007 Plan): parsing, explanations, chat."""

from __future__ import annotations

import json

from api.validation import today
from tripwise import data
from tripwise.models import TAGS


def parse_system() -> str:
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


def explain_system() -> str:
    return """You explain trip plans made by a planner to the traveller. You do not change plans.
You get JSON with the traveller's preferences and one or more plan variants (experience, balanced, saver), each
with its transport, hotel, day-by-day activities, costs and near-misses (activities left out, with the reason).
Reply with one JSON object only: {"<variant name>": "<explanation>", ...} with one key per variant given.
Each explanation is 2-4 short plain sentences (under 90 words) on why this variant suits the traveller and
what it trades off. Name at most four highlights; do not list every activity. When you mention a near-miss, give
its reason exactly as listed (budget, time or closed).
Rules: mention only activities, hotels and near-misses that appear in that variant's data, spelled as given.
Write rupee amounts as ₹ followed by a number copied exactly from that variant's data (for example ₹12400);
never add, subtract or estimate amounts. Prices are estimates. No markdown, no lists."""


def _tool(name: str, description: str, props: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": props or {}, "required": required or [], "additionalProperties": False}}}


_NAME = {"name": {"type": "string", "description": "The activity's name exactly as the traveller wrote it, even when vague "
                  "(for example \"the palace\"); never swap in a specific activity from the trip, the planner asks which one"}}
_NAMES = {"names": {"type": "array", "minItems": 1, "items": {"type": "string"},
                    "description": "Every activity meant, each name exactly as the traveller wrote it, even when vague "
                    "(for example [\"the palace\"]), or as listed in the trip when the traveller means a group or kind "
                    "of place"}}
_HOURS = {"type": "number", "minimum": 4, "maximum": 14}
KINDS = sorted({a.kind for a in data.default().attractions.values() if a.kind})   # 001 §5.5 kind

TOOLS = [
    _tool("lock_activity", "Make sure one or more activities are in the plan (keep, add, must see) when no day is named; "
          "if a day is named, use move_activity.", _NAMES, ["names"]),
    _tool("exclude_activity", "Take one or more named activities out of the plan and keep them out. A single place, even "
          "a vague one (\"the lake\"), goes here as the traveller wrote it.", _NAMES, ["names"]),
    _tool("limit_kind", "Cap how many places of a kind the plan has, only when the traveller counts or talks about a "
          "kind in the plural rather than one place: \"no masjids\" is mosque max 0, \"only one church\" is church "
          "max 1, \"just one temple and one church\" is two limits, \"too many forts\" is fort max 1. The planner "
          "keeps the best ones and replaces the rest. Masjids and dargahs are mosque; mandirs are temple. Not for one "
          "place (\"the gurudwara\": use exclude_activity or lock_activity) and not for interests (\"we don't care "
          "about nightlife\": use set_interest).",
          {"limits": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": False,
                      "properties": {"kind": {"type": "string", "enum": KINDS},
                                     "max": {"type": "integer", "minimum": 0, "maximum": 10}},
                      "required": ["kind", "max"]}}}, ["limits"]),
    _tool("set_budget", "Change the total trip budget for the whole group, in whole rupees. For a relative change "
          "(\"5000 more\") compute the new total from the current budget.",
          {"budget_total": {"type": "integer", "minimum": 1}}, ["budget_total"]),
    _tool("set_day_hours", "Change the hours out of the hotel on one day of the trip.",
          {"day": {"type": "integer", "minimum": 1}, "hours": _HOURS}, ["day", "hours"]),
    _tool("set_all_hours", "Change the hours out of the hotel on every day.", {"hours": _HOURS}, ["hours"]),
    _tool("set_hotel_tier", "Change the hotel level.", {"tier": {"type": "string", "enum": ["budget", "mid", "premium"]}}, ["tier"]),
    _tool("set_transport", "Travel by a given mode (and optionally class): direction out = the way there, ret = the way back, "
          "both only when both are meant or no direction is clear.",
          {"direction": {"type": "string", "enum": ["out", "ret", "both"]},
           "mode": {"type": "string", "enum": ["train", "bus", "flight"]},
           "class": {"type": "string", "enum": ["SL", "3A", "2A", "ACS", "Y"],
                     "description": "Train SL (sleeper), 3A or 2A; bus ACS; flight Y (economy). Omit if not said."}},
          ["direction", "mode"]),
    _tool("set_pace", "Change the pace of the trip.", {"pace": {"type": "string", "enum": ["relaxed", "balanced", "packed"]}}, ["pace"]),
    _tool("set_interest", "Change how much the traveller cares about one interest, 0 (not at all) to 5 (loves it).",
          {"interest": {"type": "string", "enum": list(TAGS)}, "weight": {"type": "integer", "minimum": 0, "maximum": 5}},
          ["interest", "weight"]),
    _tool("move_activity", "Put, move or schedule an activity on a given day of the trip (this also keeps it in the plan).",
          _NAME | {"day": {"type": "integer", "minimum": 1}}, ["name", "day"]),
    _tool("regenerate", "Plan the trip again from the current settings."),
    _tool("explain", "Answer a question about the plan, such as why an activity is or is not in it. Give the activity's "
          "name when the question is about one; otherwise leave name out.",
          {"name": {"type": ["string", "null"], "description": "The activity's name, or null for a general question"}}),
    _tool("unsupported", "Anything the other tools cannot do: booking, payments, other cities, weather, visas, "
          "restaurants, adding days, and so on.",
          {"topic": {"type": "string", "description": "What was asked, in a few words"},
           "closest": {"type": "string", "enum": ["lock_activity", "exclude_activity", "limit_kind", "set_budget", "set_day_hours",
                                                  "set_all_hours", "set_hotel_tier", "set_transport", "set_pace",
                                                  "set_interest", "move_activity", "explain", "none"]}},
          ["topic", "closest"]),
]


def chat_system(context: dict) -> str:
    return f"""You are the assistant inside a trip planner. You never write or edit plans yourself: you call tools,
and the planner makes the new plan. Call a tool for every message, choosing only from the tools given. Use the
activity names as the traveller wrote them. When the traveller counts or talks about a kind of place in the
plural (churches, temples, beaches, forts and so on), use limit_kind: the planner also keeps out places of that
kind that are not in the plan yet. Day numbers start at 1. If a message asks for something no tool can do, call unsupported. If it asks a question,
call explain.
The current trip (JSON): {json.dumps(context, ensure_ascii=False)}"""


def reply_system() -> str:
    return """You write the planner assistant's short reply (1-3 sentences, plain text, no markdown) to the
traveller, from the JSON facts given: what the planner changed or found. Describe only what the facts say
changed: "applied" (activities removed and kept out, now always included or moved, kinds limited, settings
changed) and "changes" (added, removed and moved activities, hotel and transport, cost). Do not guess what the
traveller asked for and do not say a request was done; just say what changed. Mention only activities and hotels
named in the facts, at most four names in all; summarise the rest (for example "and reshuffled the days"). Write
rupee amounts as ₹ followed by a number copied exactly from the facts; never compute new amounts. old_total and
new_total are the plan's estimated cost, not the budget; budget_total is the budget. Prices are estimates. Do not
promise anything the facts do not say."""
