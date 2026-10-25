"""Chat history per trip (API-FR-10). Sending messages is added by Feature 007."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api import db
from api.auth import current_user
from api.routers.trips import own_trip

router = APIRouter(prefix="/trips/{trip_id}/chat", tags=["chat"])


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
