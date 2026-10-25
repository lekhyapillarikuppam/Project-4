"""AI endpoints (Feature 007). Planning never depends on these (AI-FR-06)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends

from api.ai import groq_client, parse as parser
from api.auth import current_user
from api.errors import ApiError

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/parse-prefs")
async def parse_prefs(body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    text = body.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ApiError(422, "Describe your trip in 1–2000 characters.", "invalid", {"text": "1–2000 characters."})
    try:
        return await asyncio.get_running_loop().run_in_executor(None, parser.parse, text.strip())
    except groq_client.Unavailable:
        raise ApiError(503, "The assistant is unavailable right now. Use the sliders instead.", "unavailable")
    except parser.Unparseable:
        raise ApiError(422, "Couldn't understand that, please use the sliders.", "unparseable")
