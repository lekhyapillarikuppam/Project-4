"""Distances and the OpenRouteService client (001 Plan §2.2).

Every ORS response is cached in data/raw/ors/ under a hash of the request, so
pairs and matrices can be rebuilt without new API calls (001 Spec §5.9).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ORS_CACHE = ROOT / "data" / "raw" / "ors"
ORS_BASE = "https://api.openrouteservice.org/v2"
SNAP_RADIUS_M = 2000   # airports and stations may sit away from the road graph


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _key() -> str:
    load_dotenv(ROOT / ".env")
    return os.environ["ORS_API_KEY"]


def _cached_post(kind: str, path: str, body: dict, legacy_name: str | None = None) -> dict:
    name = legacy_name or f"{kind}_{hashlib.md5(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]}.json"
    cache = ORS_CACHE / name
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    r = requests.post(f"{ORS_BASE}/{path}", headers={"Authorization": _key()}, json=body, timeout=120)
    data = r.json()
    if r.status_code != 200 or "error" in data:
        raise RuntimeError(f"ORS {path} failed ({r.status_code}): {data.get('error')}")
    ORS_CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


def route(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """Driving distance (km) and free-flow time (min) from a to b, as (lat, lon) pairs."""
    start, end = f"{a[1]},{a[0]}", f"{b[1]},{b[0]}"
    legacy = f"dir_{hashlib.md5((start + end).encode()).hexdigest()[:12]}.json"
    body = {"coordinates": [[a[1], a[0]], [b[1], b[0]]], "radiuses": [SNAP_RADIUS_M, SNAP_RADIUS_M]}
    d = _cached_post("dir", "directions/driving-car/geojson", body, legacy)
    s = d["features"][0]["properties"]["summary"]
    return s.get("distance", 0) / 1000, s.get("duration", 0) / 60


def matrix(points: list[tuple[float, float]]) -> tuple[list[list[float]], list[list[float]]]:
    """Driving distance (km) and free-flow time (min) between every pair of (lat, lon) points."""
    body = {"locations": [[lon, lat] for lat, lon in points], "metrics": ["distance", "duration"], "units": "km"}
    d = _cached_post("matrix", "matrix/driving-car", body)
    km = [[float(x) if x is not None else float("nan") for x in row] for row in d["distances"]]
    mins = [[float(x) / 60 if x is not None else float("nan") for x in row] for row in d["durations"]]
    return km, mins
