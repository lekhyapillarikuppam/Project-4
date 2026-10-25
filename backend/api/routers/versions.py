"""Plan versions (API-FR-07, API-FR-08, API-FR-09): select, replan, list, get, restore, trade-offs.

Versions are immutable. Each stores the plan and the request it was planned from; replans build on the
newest version's request. Chat (007) changes plans only through replan (Constitution II).
"""

from __future__ import annotations

import copy

import psycopg
from fastapi import APIRouter, Body, Depends

from api import db, solver
from api.auth import current_user
from api.errors import ApiError, not_found
from api.routers.trips import own_trip
from api.validation import check_trip
from tripwise.models import Plan, TripRequest, dump
from tripwise.tradeoffs import trade_offs, variant_at

router = APIRouter(prefix="/trips/{trip_id}", tags=["versions"])
CHANGE_KEYS = {"locks", "excludes", "budget_total", "prefs", "pins", "day_hours", "transport"}
SOURCES = {"replan", "chat"}


def _summary(row: dict) -> dict:
    p = row["plan"]
    return {"version": row["version"], "source": row["source"], "note": row["note"], "changes": row["changes"],
            "variant": p.get("variant"), "total": p["budget"]["total"], "value": p["value"],
            "created_at": row["created_at"].isoformat()}


def _full(row: dict) -> dict:
    return _summary(row) | {"plan": row["plan"], "request": row["request"]}


def add_version(trip_id: str, plan: dict, request: dict, source: str, changes: dict | None, note: str | None,
                variant: str | None = None) -> dict:
    for _ in range(3):
        try:
            row = db.one("INSERT INTO {s}.plan_versions (trip_id, version, plan, request, source, changes, note) "
                         "SELECT %s, COALESCE(MAX(version), 0) + 1, %s, %s, %s, %s, %s FROM {s}.plan_versions "
                         "WHERE trip_id = %s RETURNING *",
                         trip_id, db.jsonb(plan), db.jsonb(request), source,
                         db.jsonb(changes) if changes is not None else None, note, trip_id)
            break
        except psycopg.errors.UniqueViolation:     # two writers took the same number; retry
            continue
    else:
        raise ApiError(409, "Another change was saved at the same time; please retry.", "conflict")
    db.run("UPDATE {s}.trips SET request = %s, updated_at = now()" + (", selected_variant = %s" if variant else "")
           + " WHERE id::text = %s", *([db.jsonb(request)] + ([variant] if variant else []) + [trip_id]))
    return row


def latest(trip_id: str) -> dict | None:
    return db.one("SELECT * FROM {s}.plan_versions WHERE trip_id::text = %s ORDER BY version DESC LIMIT 1", trip_id)


@router.post("/select", status_code=201)
def select(trip_id: str, body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    trip = own_trip(trip_id, user)
    variant = body.get("variant")
    res = trip["result"]
    if res.get("status") != "ok":
        raise ApiError(409, "This trip has no plan to choose; change the budget or dates first.", "no_plan")
    plan = next((p for p in res["variants"] if p.get("variant") == variant), None)
    if plan is None:
        shown = [p["variant"] for p in res["variants"]]
        raise ApiError(422, f"Choose one of: {', '.join(shown)}.", "invalid", {"variant": f"One of {', '.join(shown)}."})
    return _full(add_version(trip_id, plan, trip["request"], "select", None, f"chose {variant}", variant))


def apply_changes(request: dict, changes: dict) -> dict:
    unknown = set(changes) - CHANGE_KEYS
    if unknown:
        raise ApiError(422, f"Unsupported change(s): {', '.join(sorted(unknown))}.", "invalid",
                       {k: "Not a supported change." for k in unknown})
    new = copy.deepcopy(request)
    for k in ("locks", "excludes", "budget_total"):
        if k in changes:
            new[k] = changes[k]
    for k in ("pins", "day_hours"):          # merged key by key; a null value removes the entry
        if k in changes:
            if not isinstance(changes[k], dict):
                raise ApiError(422, f"{k} must be an object.", "invalid", {k: "An object."})
            merged = {str(a): b for a, b in (new.get(k) or {}).items()}
            for a, b in changes[k].items():
                if b is None:
                    merged.pop(str(a), None)
                else:
                    merged[str(a)] = b
            new[k] = merged
    if "transport" in changes:             # each direction replaced; null clears it
        t = changes["transport"]
        if t is not None and not isinstance(t, dict):
            raise ApiError(422, "transport must be an object.", "invalid", {"transport": "An object."})
        cur = dict(new.get("transport") or {})
        for k, v in (t or {}).items():
            cur[k] = v
        new["transport"] = {k: v for k, v in cur.items() if v is not None} or None
    if "prefs" in changes:
        patch = changes["prefs"]
        if not isinstance(patch, dict):
            raise ApiError(422, "prefs must be an object.", "invalid", {"prefs": "An object."})
        for k, v in patch.items():
            if k in ("interests", "modes") and isinstance(v, dict) and isinstance(new["prefs"].get(k), dict):
                new["prefs"][k] = new["prefs"][k] | v
            else:
                new["prefs"][k] = v
    return new


async def replan_request(trip_id: str, user: dict, changes: dict, source: str, note: str | None) -> dict:
    trip = own_trip(trip_id, user)
    if not trip["selected_variant"]:
        raise ApiError(409, "Choose a plan first.", "not_selected")
    if not isinstance(changes, dict) or not changes:
        raise ApiError(422, "Give at least one change.", "invalid", {"changes": "At least one change."})
    base = latest(trip_id)
    merged = apply_changes(base["request"] if base else trip["request"], changes)
    req: TripRequest = check_trip(merged)
    res = await solver.solve(variant_at, req, trip["selected_variant"])
    if not isinstance(res, Plan):
        out = dump(res)
        if out.get("status") == "error":
            raise ApiError(500, "The planner produced an invalid plan; it was withheld.", "internal_validation_failed")
        raise ApiError(409, out.get("message", "No plan fits these changes."), "infeasible", extra={"result": out})
    return _full(add_version(trip_id, dump(res), req.model_dump(mode="json", by_alias=True), source, changes, note))


@router.post("/replan", status_code=201)
async def replan(trip_id: str, body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    source = body.get("source", "replan")
    if source not in SOURCES:
        raise ApiError(422, "source is replan or chat.", "invalid", {"source": "replan or chat"})
    return await replan_request(trip_id, user, body.get("changes"), source, body.get("note"))


@router.get("/versions")
def list_versions(trip_id: str, user: dict = Depends(current_user)) -> list[dict]:
    own_trip(trip_id, user, "id")
    rows = db.all_("SELECT * FROM {s}.plan_versions WHERE trip_id::text = %s ORDER BY version", trip_id)
    return [_summary(r) for r in rows]


@router.get("/versions/{version}")
def get_version(trip_id: str, version: int, user: dict = Depends(current_user)) -> dict:
    own_trip(trip_id, user, "id")
    row = db.one("SELECT * FROM {s}.plan_versions WHERE trip_id::text = %s AND version = %s", trip_id, version)
    if row is None:
        raise not_found("Version not found.")
    return _full(row)


@router.post("/versions/{version}/restore", status_code=201)
def restore(trip_id: str, version: int, user: dict = Depends(current_user)) -> dict:
    own_trip(trip_id, user, "id")
    old = db.one("SELECT * FROM {s}.plan_versions WHERE trip_id::text = %s AND version = %s", trip_id, version)
    if old is None:
        raise not_found("Version not found.")
    return _full(add_version(trip_id, old["plan"], old["request"], "restore", None, f"restored version {version}"))


@router.get("/tradeoffs")
async def tradeoffs(trip_id: str, variant: str | None = None, user: dict = Depends(current_user)) -> dict:
    trip = own_trip(trip_id, user)
    variant = variant or trip["selected_variant"] or "balanced"
    if variant not in ("experience", "balanced", "saver"):
        raise ApiError(422, "variant is experience, balanced or saver.", "invalid", {"variant": "experience, balanced or saver"})
    req = TripRequest.model_validate(trip["request"])
    key = req.request_hash()
    cache = trip["tradeoffs"] or {}
    hit = cache.get(variant)
    if hit and hit.get("request_hash") == key:
        return hit["data"] | {"cached": True}
    out = dump(await solver.solve(trade_offs, req, variant))
    cache[variant] = {"request_hash": key, "data": out}
    db.run("UPDATE {s}.trips SET tradeoffs = %s WHERE id::text = %s", db.jsonb(cache), trip_id)
    return out | {"cached": False}
