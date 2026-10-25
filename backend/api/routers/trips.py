"""Trips (API-FR-05, API-FR-06): create + plan, list, get, rename, duplicate, delete.

Every query filters on the caller's user id; another user's trip id is a 404 (API-FR-02).
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Response

from api import db, solver
from api.auth import current_user
from api.errors import ApiError, not_found
from api.validation import check_trip, today
from tripwise.models import dump
from tripwise.variants import plan_variants

router = APIRouter(prefix="/trips", tags=["trips"])


def trip_out(row: dict) -> dict:
    return {"id": str(row["id"]), "name": row["name"], "request": row["request"], "result": row["result"],
            "selected_variant": row["selected_variant"], "start_date": row["start_date"].isoformat(),
            "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat()}


def own_trip(trip_id: str, user: dict, cols: str = "*") -> dict:
    row = db.one(f"SELECT {cols} FROM {{s}}.trips WHERE id::text = %s AND user_id = %s", trip_id, user["id"])
    if row is None:
        raise not_found("Trip not found.")
    return row


def default_name(req) -> str:
    from tripwise import data
    c = data.default().cities
    return f"{c[req.origin].name} to {c[req.destination].name}, {req.start_date:%d %b %Y}"


@router.post("", status_code=201)
async def create_trip(body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    req = check_trip(body)
    result = dump(await solver.solve(plan_variants, req))
    if result.get("status") == "error":
        raise ApiError(500, "The planner produced an invalid plan; it was withheld.", "internal_validation_failed")
    name = (body.get("name") or "").strip()[:120] or default_name(req)
    row = db.one("INSERT INTO {s}.trips (user_id, name, request, result, start_date) VALUES (%s, %s, %s, %s, %s) RETURNING *",
                 user["id"], name, db.jsonb(req.model_dump(mode="json")), db.jsonb(result), req.start_date)
    return trip_out(row)


@router.get("")
def list_trips(when: str | None = None, user: dict = Depends(current_user)) -> list[dict]:
    if when not in (None, "upcoming", "past"):
        raise ApiError(422, "when is upcoming or past.", "invalid", {"when": "upcoming or past"})
    sql = ("SELECT id, name, request, result->>'status' AS status, selected_variant, start_date, created_at, updated_at "
           "FROM {s}.trips WHERE user_id = %s")
    args = [user["id"]]
    if when == "upcoming":
        sql += " AND start_date >= %s ORDER BY start_date, created_at"
        args.append(today())
    elif when == "past":
        sql += " AND start_date < %s ORDER BY start_date DESC, created_at DESC"
        args.append(today())
    else:
        sql += " ORDER BY start_date, created_at"
    rows = db.all_(sql, *args)
    return [{"id": str(r["id"]), "name": r["name"], "origin": r["request"]["origin"],
             "destination": r["request"]["destination"], "start_date": r["start_date"].isoformat(),
             "end_date": r["request"]["end_date"], "people": r["request"]["people"],
             "budget_total": r["request"]["budget_total"], "status": r["status"],
             "selected_variant": r["selected_variant"], "updated_at": r["updated_at"].isoformat()} for r in rows]


@router.get("/{trip_id}")
def get_trip(trip_id: str, user: dict = Depends(current_user)) -> dict:
    return trip_out(own_trip(trip_id, user))


@router.patch("/{trip_id}")
def rename_trip(trip_id: str, body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    name = body.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ApiError(422, "Give the trip a name of 1–120 characters.", "invalid", {"name": "1–120 characters."})
    own_trip(trip_id, user, "id")
    row = db.one("UPDATE {s}.trips SET name = %s, updated_at = now() WHERE id::text = %s AND user_id = %s RETURNING *",
                 name.strip(), trip_id, user["id"])
    return trip_out(row)


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: str, user: dict = Depends(current_user)) -> Response:
    if db.run("DELETE FROM {s}.trips WHERE id::text = %s AND user_id = %s", trip_id, user["id"]) == 0:
        raise not_found("Trip not found.")
    return Response(status_code=204)     # versions and chat go with it (ON DELETE CASCADE)


@router.post("/{trip_id}/duplicate")
def duplicate_trip(trip_id: str, user: dict = Depends(current_user)) -> dict:
    """A copy of the request for the New trip form; nothing is created (API-FR-06)."""
    row = own_trip(trip_id, user, "request")
    req = dict(row["request"])
    form = {k: req[k] for k in ("origin", "destination", "start_date", "end_date", "people", "budget_total", "prefs",
                                "locks", "excludes")}
    return {"request": form}
