"""Chat per trip: history (API-FR-10) and sending a message (AI-FR-03–AI-FR-05)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Body, Depends

from api import db
from api.ai import chat as assistant
from api.auth import current_user
from api.errors import ApiError
from api.routers.trips import own_trip
from api.routers.versions import latest
from tripwise import config

router = APIRouter(prefix="/trips/{trip_id}/chat", tags=["chat"])
_sent: dict[str, deque] = defaultdict(deque)     # user id -> send times in the last hour (per process, AI-FR-07)


def check_rate(user_id: str) -> None:
    now, window = time.monotonic(), 3600.0
    q = _sent[user_id]
    while q and now - q[0] >= window:
        q.popleft()
    limit = config.default().chat["rate_per_hour"]
    if len(q) >= limit:
        wait = int(window - (now - q[0])) // 60 + 1
        raise ApiError(429, f"You've sent {limit} messages in the last hour. Please try again in about {wait} min.",
                       "rate_limited")
    q.append(now)


def message_out(r: dict) -> dict:
    return {"id": r["id"], "role": r["role"], "text": r["text"], "actions": r["actions"], "version": r["version"],
            "created_at": r["created_at"].isoformat()}


def add_message(trip_id: str, role: str, text: str, actions=None, version: int | None = None) -> dict:
    row = db.one("INSERT INTO {s}.chat_messages (trip_id, role, text, actions, version) VALUES (%s, %s, %s, %s, %s) "
                 "RETURNING *", trip_id, role, text, db.jsonb(actions) if actions is not None else None, version)
    return message_out(row)


@router.get("")
def history(trip_id: str, user: dict = Depends(current_user)) -> list[dict]:
    own_trip(trip_id, user, "id")
    return [message_out(r) for r in db.all_("SELECT * FROM {s}.chat_messages WHERE trip_id::text = %s ORDER BY id", trip_id)]


@router.post("", status_code=201)
async def send(trip_id: str, body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    """One chat message: the assistant replies and may create a new version (source "chat")."""
    text = body.get("message")
    if not isinstance(text, str) or not text.strip() or len(text) > 1000:
        raise ApiError(422, "Write a message of 1–1000 characters.", "invalid", {"message": "1–1000 characters."})
    trip = own_trip(trip_id, user)
    check_rate(str(user["id"]))
    base = latest(trip_id)
    if not trip["selected_variant"] or base is None:
        raise ApiError(409, "Choose a plan first.", "not_selected")
    history = db.all_("SELECT role, text FROM {s}.chat_messages WHERE trip_id::text = %s ORDER BY id", trip_id)
    mine = add_message(trip_id, "user", text.strip())
    out = await assistant.handle(trip, base, user, text.strip(), history)
    v = out["version"]
    reply = add_message(trip_id, "assistant", out["text"], out["actions"], v["version"] if v else None)
    return {"user": mine, "assistant": reply, "version": v}
