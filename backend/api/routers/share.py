"""Read-only share links (API-FR-14; FR-048; Constitution Article VIII.2 exception).

The owner creates (or gets back) one token per trip and can turn it off. Anyone with the token reads the newest plan
and the trip facts, nothing else. The token is stored as is: POST must return the existing link, and a hash would
only hide the link from someone who can already read the plan in the database.
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Request, Response

from api import db
from api.auth import current_user
from api.errors import ApiError, not_found
from api.routers.trips import own_trip
from api.routers.versions import latest
from tripwise import config

router = APIRouter(tags=["share"])
_seen: dict[str, deque] = defaultdict(deque)      # client address -> public reads in the last minute (per process)


def check_rate(addr: str) -> None:
    now, window = time.monotonic(), 60.0
    q = _seen[addr]
    while q and now - q[0] >= window:
        q.popleft()
    if len(q) >= config.default().share["rate_per_minute"]:
        raise ApiError(429, "Too many requests for shared plans. Please try again in a minute.", "rate_limited")
    q.append(now)


@router.post("/trips/{trip_id}/share")
def share(trip_id: str, user: dict = Depends(current_user)) -> dict:
    own_trip(trip_id, user, "id")
    if latest(trip_id) is None:
        raise ApiError(409, "Choose a plan before sharing it.", "not_selected")
    token = secrets.token_urlsafe(config.default().share["token_bytes"])
    row = db.one("INSERT INTO {s}.trip_shares (trip_id, token) VALUES (%s, %s) "
                 "ON CONFLICT (trip_id) DO UPDATE SET trip_id = EXCLUDED.trip_id RETURNING token", trip_id, token)
    return {"token": row["token"], "url_path": f"/s/{row['token']}"}


@router.delete("/trips/{trip_id}/share", status_code=204)
def unshare(trip_id: str, user: dict = Depends(current_user)) -> Response:
    own_trip(trip_id, user, "id")
    db.run("DELETE FROM {s}.trip_shares WHERE trip_id = %s", trip_id)
    return Response(status_code=204)


@router.get("/shared/{token}")
def shared(token: str, request: Request) -> dict:
    check_rate(request.client.host if request.client else "unknown")
    row = db.one("SELECT t.id, t.name, t.request FROM {s}.trip_shares s JOIN {s}.trips t ON t.id = s.trip_id "
                 "WHERE s.token = %s", token)
    v = latest(str(row["id"])) if row else None
    if v is None:
        raise not_found("This shared plan isn't available.")
    plan = {k: x for k, x in v["plan"].items() if k != "request_hash"}
    r = row["request"]
    return {"name": row["name"], "origin": r["origin"], "destination": r["destination"], "start_date": r["start_date"],
            "end_date": r["end_date"], "people": r["people"], "budget_total": r["budget_total"],
            "version_created_at": v["created_at"].isoformat(), "plan": plan}
