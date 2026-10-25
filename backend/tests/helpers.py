"""Shared test helpers: the Feature 001 fixture dataset and request builders."""

from __future__ import annotations

from pathlib import Path

from tripwise import config
from tripwise.data import Hub, load_cached
from tripwise.models import TripRequest
from tripwise.timemodel import Option

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "datatools" / "tests" / "fixtures" / "valid"
CFG = config.default()


def fixture_ds():
    return load_cached(str(FIXTURE))


def request(**over) -> TripRequest:
    body = {
        "origin": "AGR", "destination": "JAI", "start_date": "2026-12-14", "end_date": "2026-12-17",
        "people": 2, "budget_total": 40000,
        "prefs": {"daily_hours_out": 9, "pace": "balanced", "comfort": "mid", "avoid_crowds": False, "modes": {},
                  "interests": {t: 0 for t in ("nature", "adventure", "food", "history", "culture", "spiritual",
                                               "shopping", "relaxation", "nightlife")} | {"history": 5, "culture": 3}},
        "locks": [], "excludes": [],
    }
    prefs = over.pop("prefs", {})
    body.update(over)
    body["prefs"] = body["prefs"] | prefs
    return TripRequest.model_validate(body)


def hub(access_minutes: int, cost: int = 100, mode: str = "train") -> Hub:
    return Hub("JAI", mode, "Test hub", "", 5.0, access_minutes, cost)


def option(mode: str, minutes: int, dest_access: int, overnight: bool, direction: str = "out", km: float = 100.0) -> Option:
    return Option(direction, mode, "Y" if mode == "flight" else "3A", minutes, km, overnight, 0.6, False,
                  hub(dest_access, mode=mode), hub(15, mode=mode))
