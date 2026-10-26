"""Trip input checks (API-FR-04; FR-001–FR-005) with field-level 422 messages.

Checks run on the raw body so every problem is reported at once with a plain message, then the engine's
TripRequest is built. "Today" is the date in India (UTC+05:30, A-06).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from api.errors import ApiError
from tripwise import config, data
from tripwise.models import TAGS, TripRequest

IST = timezone(timedelta(hours=5, minutes=30))
PACES = ("relaxed", "balanced", "packed")
COMFORTS = ("budget", "mid", "premium")
MODES = ("train", "bus", "flight")
MODE_PREFS = ("preferred", "neutral", "avoid")
DEFAULT_PREFS = {"daily_hours_out": 9, "interests": {t: 0 for t in TAGS} | {"history": 3, "culture": 3, "food": 3},
                 "pace": "balanced", "comfort": "mid", "modes": {m: "neutral" for m in MODES}, "avoid_crowds": False}
# An unsaved profile (API-FR-03): nothing chosen yet. Not valid for planning; the user picks hours, pace and comfort.
BLANK_PREFS = {"daily_hours_out": None, "interests": {t: 0 for t in TAGS}, "pace": None, "comfort": None,
               "modes": {m: "neutral" for m in MODES}, "avoid_crowds": False}


def today() -> date:
    return datetime.now(IST).date()


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_prefs(p, errs: dict, prefix: str = "prefs") -> dict:
    """Validate a prefs object; returns it normalised (all nine interests, all three modes)."""
    a = config.default().api
    if not isinstance(p, dict):
        errs[prefix] = "Preferences are missing."
        return {}
    out = {}
    lo, hi = a["hours_out"]
    h = p.get("daily_hours_out", DEFAULT_PREFS["daily_hours_out"])
    if not _num(h) or not lo <= h <= hi:
        errs[f"{prefix}.daily_hours_out"] = f"Hours out must be between {lo} and {hi}."
    out["daily_hours_out"] = h
    interests = p.get("interests")
    if not isinstance(interests, dict):
        errs[f"{prefix}.interests"] = "Set at least one interest."
        interests = {}
    unknown = [k for k in interests if k not in TAGS]
    if unknown:
        errs[f"{prefix}.interests"] = f"Unknown interest(s): {', '.join(unknown)}."
    norm = {}
    for t in TAGS:
        w = interests.get(t, 0)
        if not isinstance(w, int) or isinstance(w, bool) or not 0 <= w <= 5:
            errs[f"{prefix}.interests.{t}"] = "Each interest weight is a whole number from 0 to 5."
            w = 0
        norm[t] = w
    if not unknown and all(v == 0 for v in norm.values()) and f"{prefix}.interests" not in errs:
        errs[f"{prefix}.interests"] = "Give at least one interest a weight above 0."
    out["interests"] = norm
    for key, allowed, label in (("pace", PACES, "Pace"), ("comfort", COMFORTS, "Stay comfort")):
        v = p.get(key, DEFAULT_PREFS[key])
        if v not in allowed:
            errs[f"{prefix}.{key}"] = f"{label} must be one of: {', '.join(allowed)}."
        out[key] = v
    modes = p.get("modes", {}) or {}
    if not isinstance(modes, dict):
        errs[f"{prefix}.modes"] = "Transport modes are not valid."
        modes = {}
    norm_m = {}
    for m in MODES:
        v = modes.get(m, "neutral")
        if v not in MODE_PREFS:
            errs[f"{prefix}.modes.{m}"] = f"Choose preferred, neutral or avoid for {m}."
        norm_m[m] = v
    extra = [m for m in modes if m not in MODES]
    if extra:
        errs[f"{prefix}.modes"] = f"Unknown mode(s): {', '.join(extra)}."
    if all(v == "avoid" for v in norm_m.values()):
        errs[f"{prefix}.modes"] = "At least one transport mode must not be avoided."
    out["modes"] = norm_m
    ac = p.get("avoid_crowds", False)
    if not isinstance(ac, bool):
        errs[f"{prefix}.avoid_crowds"] = "Avoid crowds is on or off."
    out["avoid_crowds"] = bool(ac)
    return out


def prefs_or_422(p) -> dict:
    errs: dict = {}
    out = check_prefs(p, errs)
    if errs:
        raise ApiError(422, "Some fields are not valid.", "invalid", errs)
    return out


def _date(v, field: str, errs: dict) -> date | None:
    try:
        return date.fromisoformat(v)
    except (TypeError, ValueError):
        errs[field] = "Use a date in YYYY-MM-DD form."
        return None


def check_trip(body: dict) -> TripRequest:
    """The trip form → a TripRequest, or 422 with every field problem."""
    if not isinstance(body, dict):
        raise ApiError(422, "The request body must be a JSON object.", "invalid")
    a = config.default().api
    ds = data.default()
    errs: dict = {}
    o, d = body.get("origin"), body.get("destination")
    if o not in ds.cities:
        errs["origin"] = "Choose one of the 15 supported cities."
    if d not in ds.cities:
        errs["destination"] = "Choose one of the 15 supported cities."
    elif o == d:
        errs["destination"] = "Destination must differ from origin."
    start = _date(body.get("start_date"), "start_date", errs)
    end = _date(body.get("end_date"), "end_date", errs)
    t = today()
    if start:
        if start < t + timedelta(days=1):
            errs["start_date"] = "The trip must start tomorrow or later."
        elif start > t + timedelta(days=a["max_days_ahead"]):
            errs["start_date"] = f"The trip must start within {a['max_days_ahead']} days."
    lo, hi = a["trip_days"]
    if start and end and not lo <= (end - start).days + 1 <= hi:
        errs["end_date"] = f"A trip lasts {lo} to {hi} days (start and end included)."
    people = body.get("people")
    plo, phi = a["people"]
    if not isinstance(people, int) or isinstance(people, bool) or not plo <= people <= phi:
        errs["people"] = f"Group size is {plo} to {phi} people."
        people = None
    total, per = body.get("budget_total"), body.get("budget_per_person")
    if (total is None) == (per is None):
        errs["budget_total"] = "Give a total budget or a per-person budget."
    else:
        val = total if total is not None else per
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            errs["budget_total" if total is not None else "budget_per_person"] = "Budget is a whole number of rupees."
        elif people:
            total = total if total is not None else per * people
            field = "budget_total" if body.get("budget_total") is not None else "budget_per_person"
            if total < a["budget_min_per_person"] * people:
                errs[field] = f"The budget must be at least ₹{a['budget_min_per_person']:,} per person."
            elif total > a["budget_max_total"]:
                errs[field] = "The total budget can be at most ₹10,00,000."
    prefs = check_prefs(body.get("prefs"), errs)
    locks, excludes = body.get("locks") or [], body.get("excludes") or []
    for key, ids in (("locks", locks), ("excludes", excludes)):
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            errs[key] = "A list of attraction ids."
        elif d in ds.cities:
            bad = [i for i in ids if i not in ds.attractions or ds.attractions[i].city_id != d]
            if bad:
                errs[key] = f"Not attractions of {ds.cities[d].name}: {', '.join(bad)}."
    if isinstance(locks, list) and isinstance(excludes, list) and set(locks) & set(excludes):
        errs["locks"] = "An attraction cannot be both locked and excluded."
    n_days = (end - start).days + 1 if start and end else None
    pins = body.get("pins") or {}
    if not isinstance(pins, dict):
        errs["pins"] = "Pins map attraction ids to day numbers."
        pins = {}
    for aid, day in pins.items():
        if d in ds.cities and (aid not in ds.attractions or ds.attractions[aid].city_id != d):
            errs["pins"] = f"Not an attraction of {ds.cities[d].name}: {aid}."
        elif not isinstance(day, int) or isinstance(day, bool) or (n_days and not 1 <= day <= n_days):
            errs["pins"] = f"Day must be between 1 and {n_days}."
        elif isinstance(excludes, list) and aid in excludes:
            errs["pins"] = "An attraction cannot be both pinned and excluded."
    day_hours = body.get("day_hours") or {}
    if not isinstance(day_hours, dict):
        errs["day_hours"] = "Day hours map day numbers to hours."
        day_hours = {}
    hlo, hhi = a["hours_out"]
    clean_hours = {}
    for k, v in day_hours.items():
        try:
            day = int(k)
        except (TypeError, ValueError):
            errs["day_hours"] = "Day hours map day numbers to hours."
            continue
        if n_days and not 1 <= day <= n_days:
            errs["day_hours"] = f"Day must be between 1 and {n_days}."
        elif not _num(v) or not hlo <= v <= hhi:
            errs["day_hours"] = f"Hours out must be between {hlo} and {hhi}."
        else:
            clean_hours[day] = v
    transport = body.get("transport") or None
    if transport is not None:
        if not isinstance(transport, dict) or set(transport) - {"out", "ret"}:
            errs["transport"] = "Transport is {out?, ret?} with a mode and class."
        else:
            for key, j in transport.items():
                if j is None:
                    continue
                if not isinstance(j, dict) or j.get("mode") not in MODES or (j.get("mode"), j.get("class")) not in ds.fares:
                    errs[f"transport.{key}"] = "Choose a valid mode and class (train SL/3A/2A, bus ACS, flight Y)."
            transport = {k: v for k, v in transport.items() if v is not None} or None
    if errs:
        raise ApiError(422, "Some fields are not valid.", "invalid", errs)
    return TripRequest.model_validate({"origin": o, "destination": d, "start_date": start, "end_date": end,
                                       "people": people, "budget_total": total, "prefs": prefs,
                                       "locks": locks, "excludes": excludes, "pins": pins, "day_hours": clean_hours,
                                       "transport": transport})
