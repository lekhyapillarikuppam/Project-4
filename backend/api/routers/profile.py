"""Saved preference profile (API-FR-03; FR-042, FR-007)."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from api import db
from api.auth import current_user
from api.validation import BLANK_PREFS, prefs_or_422

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def get_profile(user: dict = Depends(current_user)) -> dict:
    row = db.one("SELECT prefs, updated_at FROM {s}.profiles WHERE user_id = %s", user["id"])
    if row is None:
        return {"prefs": BLANK_PREFS, "saved": False}
    return {"prefs": row["prefs"], "saved": True, "updated_at": row["updated_at"].isoformat()}


@router.put("")
def put_profile(body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    prefs = prefs_or_422(body.get("prefs"))
    row = db.one("INSERT INTO {s}.profiles (user_id, prefs) VALUES (%s, %s) "
                 "ON CONFLICT (user_id) DO UPDATE SET prefs = EXCLUDED.prefs, updated_at = now() RETURNING updated_at",
                 user["id"], db.jsonb(prefs))
    return {"prefs": prefs, "saved": True, "updated_at": row["updated_at"].isoformat()}
