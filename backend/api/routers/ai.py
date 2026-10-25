"""AI endpoints (Feature 007). Planning never depends on these (AI-FR-06)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends

from api import db
from api.ai import explain as explainer, groq_client, parse as parser
from api.auth import current_user
from api.errors import ApiError
from api.routers.trips import own_trip

router = APIRouter(tags=["ai"])
UNAVAILABLE_NOTICE = "Explanations are unavailable right now; the plans themselves are unaffected."


@router.post("/ai/parse-prefs")
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


@router.get("/trips/{trip_id}/explanations")
async def explanations(trip_id: str, user: dict = Depends(current_user)) -> dict:
    """Explanations of all variants (AI-FR-02), generated once and cached in trips.result.explanations."""
    trip = own_trip(trip_id, user, "request, result")
    result = trip["result"]
    if result.get("status") != "ok":
        raise ApiError(409, "This trip has no plans to explain.", "infeasible")
    if result.get("explanations"):
        return {"status": "ok", **result["explanations"], "cached": True}
    try:
        out = await asyncio.get_running_loop().run_in_executor(None, explainer.explain, trip["request"], result["variants"])
    except groq_client.Unavailable:
        return {"status": "unavailable", "notice": UNAVAILABLE_NOTICE}     # not cached: retried on the next visit
    db.run("UPDATE {s}.trips SET result = jsonb_set(result, '{explanations}', %s) WHERE id::text = %s",
           db.jsonb(out), trip_id)
    return {"status": "ok", **out, "cached": False}
