"""Public endpoints: /health, /meta, /cities."""

from __future__ import annotations

from fastapi import APIRouter

from api.errors import ApiError
from tripwise import config, data
from tripwise.models import TAGS

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "dataset_version": data.default().label}


@router.get("/meta")
def meta() -> dict:
    ds, cfg = data.default(), config.default()
    a = cfg.api
    return {"dataset_version": ds.label, "estimate_label": ds.estimate_label(), "interests": list(TAGS),
            "paces": list(cfg.pace.keys()), "comforts": ["budget", "mid", "premium"],
            "modes": ["train", "bus", "flight"], "mode_prefs": ["preferred", "neutral", "avoid"],
            "limits": {"trip_days": list(a["trip_days"]), "people": list(a["people"]), "hours_out": list(a["hours_out"]),
                       "interest_weight": [0, 5], "budget_min_per_person": a["budget_min_per_person"],
                       "budget_max_total": a["budget_max_total"], "max_days_ahead": a["max_days_ahead"]}}


@router.get("/cities")
def cities() -> list[dict]:
    return [{"code": c.city_id, "name": c.name, "lat": c.lat, "lon": c.lon} for c in data.default().cities.values()]


@router.get("/cities/{code}/places")
def places(code: str) -> dict:
    """Coordinates of a city's attractions and hotels, for the plan map (UI-FR-05). Public reference data."""
    ds = data.default()
    if code not in ds.cities:
        raise ApiError(404, "Unknown city.")
    return {"city": code,
            "attractions": [{"id": a.attraction_id, "name": a.name, "lat": a.lat, "lon": a.lon, "tags": list(a.tags)}
                            for a in ds.by_city[code]],
            "hotels": [{"id": h.hotel_id, "name": h.name, "tier": h.tier, "lat": h.lat, "lon": h.lon}
                       for h in ds.hotels.values() if h.city_id == code]}
