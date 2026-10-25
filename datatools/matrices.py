"""Build intra-city travel matrices (001 Spec §5.9, T19).

    python -m datatools.matrices [CITY ...]

For each city the nodes are its hotels, its attractions and `<CITY>-HUB-<mode>` for each hub, in that
order. Distances and free-flow times come from the OpenRouteService `driving-car` matrix; responses are
cached in data/raw/ors/ (datatools.geo), so a rebuild needs no new API calls. A city with more than
MAX_LOCATIONS nodes is fetched in blocks.

Two approximations, recorded per city in data/raw/matrices/<CITY>_approx.json:
- a pair ORS cannot route (null: a point too far from the road graph) gets the great-circle distance
  × DETOUR_FACTOR, at FALLBACK_KMH;
- distinct nodes closer than the rounding step get MIN_KM and MIN_MINUTES, so off-diagonal values stay
  positive (DATA-FR-07).
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

from datatools import geo, rules
from datatools.curation.common import read_csv

ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "data" / "curated"
APPROX_DIR = ROOT / "data" / "raw" / "matrices"
MAX_LOCATIONS = 50       # ORS public matrix request limit used here
BLOCK = 25
DETOUR_FACTOR = 1.3
FALLBACK_KMH = 25
MIN_KM = 0.1
MIN_MINUTES = 1


def nodes(city: str) -> list[tuple[str, float, float]]:
    out = [(r["hotel_id"], float(r["lat"]), float(r["lon"])) for r in read_csv(CURATED / rules.HOTELS_FILE) if r["city_id"] == city]
    out += [(r["attraction_id"], float(r["lat"]), float(r["lon"]))
            for r in read_csv(CURATED / rules.ATTRACTIONS_DIR / f"{city}.csv")]
    out += [(rules.HUB_NODE_FORMAT.format(city=city, mode=r["mode"]), float(r["lat"]), float(r["lon"]))
            for r in read_csv(CURATED / rules.HUBS_FILE) if r["city_id"] == city]
    return out


def ors_grid(points: list[tuple[float, float]]) -> tuple[list[list[float]], list[list[float]]]:
    n = len(points)
    if n <= MAX_LOCATIONS:
        return geo.matrix(points)
    km = [[math.nan] * n for _ in range(n)]
    mins = [[math.nan] * n for _ in range(n)]
    blocks = [list(range(i, min(i + BLOCK, n))) for i in range(0, n, BLOCK)]
    for a in blocks:
        for b in blocks:
            idx = a + [j for j in b if j not in a]
            sub = [points[i] for i in idx]
            body = {"locations": [[lon, lat] for lat, lon in sub], "metrics": ["distance", "duration"], "units": "km",
                    "sources": list(range(len(a))), "destinations": [idx.index(j) for j in b]}
            d = geo._cached_post("matrix", "matrix/driving-car", body)
            for si, i in enumerate(a):
                for di, j in enumerate(b):
                    dist, dur = d["distances"][si][di], d["durations"][si][di]
                    km[i][j] = float(dist) if dist is not None else math.nan
                    mins[i][j] = float(dur) / 60 if dur is not None else math.nan
    return km, mins


def build(city: str) -> tuple[dict, dict]:
    ns = nodes(city)
    pts = [(lat, lon) for _, lat, lon in ns]
    km, mins = ors_grid(pts)
    n = len(ns)
    approx = {"unroutable": [], "below_rounding": []}
    out_km = [[0.0] * n for _ in range(n)]
    out_min = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            k, m = km[i][j], mins[i][j]
            if math.isnan(k) or math.isnan(m):
                k = geo.haversine_km(*pts[i], *pts[j]) * DETOUR_FACTOR
                m = k / FALLBACK_KMH * 60
                approx["unroutable"].append([ns[i][0], ns[j][0]])
            k, m = round(k, rules.KM_DECIMALS), int(math.floor(m + 0.5))
            if k < MIN_KM or m < MIN_MINUTES:
                approx["below_rounding"].append([ns[i][0], ns[j][0]])
                k, m = max(k, MIN_KM), max(m, MIN_MINUTES)
            out_km[i][j], out_min[i][j] = k, m
    APPROX_DIR.mkdir(parents=True, exist_ok=True)
    (APPROX_DIR / f"{city}_approx.json").write_text(json.dumps(approx, indent=1), encoding="utf-8")
    return {"city_id": city, "profile": rules.MATRIX_PROFILE, "computed_on": time.strftime("%Y-%m-%d"),
            "nodes": [x[0] for x in ns], "km": out_km, "minutes_free_flow": out_min}, approx


def main(argv: list[str] | None = None) -> int:
    cities = (argv if argv is not None else sys.argv[1:]) or list(rules.CITY_CODES)
    out_dir = CURATED / rules.MATRICES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for city in cities:
        doc, approx = build(city)
        (out_dir / f"{city}.json").write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        print(city, len(doc["nodes"]), "nodes;", len(approx["unroutable"]), "unroutable,",
              len(approx["below_rounding"]), "below rounding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
