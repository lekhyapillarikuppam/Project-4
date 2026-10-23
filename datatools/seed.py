"""Seed attraction candidates for a city (001 Spec §6.1, T14).

    python -m datatools.seed <CITY> [--radius-km N]

Queries OpenTripMap for 'interesting_places' within the radius of the city centre and saves
the candidates to data/raw/seed/<CITY>.json (the API key is never written). If OpenTripMap
returns fewer than MIN_CANDIDATES places, OpenStreetMap is queried through Overpass instead.
Markets, food streets and nightlife venues are not 'interesting_places' in OpenTripMap, so
they are added from Overpass for every city. Known places neither query returns (shopping and
nightlife streets, lakes, food places) are listed by OSM id in EXTRA_OSM and fetched from Overpass.

    python -m datatools.seed <CITY> --extras-only

refetches only the EXTRA_OSM block of an existing seed file; the block records its own fetched_on.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from datatools import rules

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "raw" / "seed"
OTM = "https://api.opentripmap.com/0.1/en/places/radius"
OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "Tripwise/1.0 (UMC301 student project; lekhya.pillarikuppam@gmail.com)"}
DEFAULT_RADIUS_KM = 20
RADIUS_KM = {"GOA": 40, "HMP": 30, "MUN": 30}   # spread-out destinations
MIN_CANDIDATES = 40
# OSM objects for known places that neither query returns (streets, lakes), fetched by id.
EXTRA_OSM = {
    "BLR": ["way/48166762", "relation/10602057", "relation/10543175", "way/23133647", "relation/1857615",
            "relation/6030715", "way/27227507"],   # Church Street, Brigade Road, Commercial Street,
                                   # Gandhi Bazaar Main Road, Ulsoor Lake, Sankey Tank, 100 Feet Road (Indiranagar)
    "JAI": ["node/7068572485", "way/170101078"],   # Masala Chowk, Johari Bazar
    "VNS": ["node/2805194167", "way/26683124",    # Blue Lassi Shop, Dashashwamedh Road,
            "node/11438507361", "node/9520848117"],   # Ratneshwar Mahadev, Annapurna (OpenTripMap points are wrong)
    "AGR": ["way/1564172826"],                     # Fatehpur Sikri (outside the 20 km seed radius)
    "HMP": ["node/13381673197", "way/1128222500"],   # Hampi Mango Tree Restaurant, BABA Cafe
}
FETCHED = time.strftime("%Y-%m-%d")


def centre(city: str) -> tuple[float, float]:
    import csv
    with open(ROOT / "data" / "curated" / rules.CITIES_FILE, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["city_id"] == city:
                return float(r["lat"]), float(r["lon"])
    raise SystemExit(f"unknown city {city}")


def overpass(query: str) -> dict:
    status = None
    for attempt in range(6):
        try:   # the public server often drops connections under load
            r = requests.post(OVERPASS, data={"data": query}, headers=UA, timeout=180)
            status = r.status_code
            if r.status_code == 200:
                return r.json()
        except requests.RequestException as e:
            status = type(e).__name__
        time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"Overpass failed: {status}")


def osm_items(elements: list[dict], source: str) -> list[dict]:
    out = []
    for e in elements:
        t = e.get("tags", {})
        p = e.get("center", e)
        name = t.get("name:en") or t.get("name")
        if not name or "lat" not in p:
            continue
        out.append({"source": source, "osm": f"{e['type']}/{e['id']}", "name": name, "wikidata": t.get("wikidata"),
                    "lat": p["lat"], "lon": p["lon"], "osm_tags": t})
    return out


def extras_query(city: str) -> str:
    return ("[out:json][timeout:120];("
            + "".join(f"{t}({i});" for t, i in (x.split("/") for x in EXTRA_OSM[city]))
            + ");out center tags;")


def refresh_extras(city: str) -> dict:
    data = json.loads((SEED_DIR / f"{city}.json").read_text(encoding="utf-8"))
    q = extras_query(city)
    data["overpass"]["extras"] = {"query": q, "items": osm_items(overpass(q).get("elements", []), "overpass:extras"),
                                  "fetched_on": FETCHED}
    return data


def seed(city: str, radius_km: float) -> dict:
    lat, lon = centre(city)
    load_dotenv(ROOT / ".env")
    # The API caps a response at 500 places, so query the highest rates first and merge.
    params = {"radius": int(radius_km * 1000), "lat": lat, "lon": lon, "kinds": "interesting_places",
              "format": "json", "limit": 500}
    otm, seen = [], set()
    for rate in ("3", "2", "1"):
        r = requests.get(OTM, params={**params, "rate": rate, "apikey": os.environ["OPENTRIPMAP_API_KEY"]}, timeout=120)
        r.raise_for_status()
        for x in r.json():
            if x.get("name") and x["xid"] not in seen:
                seen.add(x["xid"])
                otm.append({"source": "opentripmap", "xid": x["xid"], "osm": x.get("osm"), "name": x["name"],
                            "wikidata": x.get("wikidata"), "kinds": x["kinds"], "rate": x["rate"],
                            "lat": x["point"]["lat"], "lon": x["point"]["lon"]})
        time.sleep(1)
    params["rate"] = "3, then 2, then 1 (merged)"
    queries = {
        "markets_food_nightlife": (
            f'[out:json][timeout:120];('
            f'nwr(around:{int(radius_km * 1000)},{lat},{lon})["amenity"="marketplace"]["name"];'
            f'nwr(around:{int(radius_km * 1000)},{lat},{lon})["shop"="mall"]["wikidata"];'
            f'nwr(around:{int(radius_km * 1000)},{lat},{lon})["amenity"~"^(nightclub|pub|bar)$"]["wikidata"];'
            f'nwr(around:{int(radius_km * 1000)},{lat},{lon})["place"~"^(neighbourhood|quarter)$"]["wikidata"]["tourism"];'
            f');out center tags;'),
    }
    if city in EXTRA_OSM:
        queries["extras"] = extras_query(city)
    if len(otm) < MIN_CANDIDATES:
        queries["fallback_attractions"] = (
            f'[out:json][timeout:120];('
            f'nwr(around:{int(radius_km * 1000)},{lat},{lon})["tourism"~"^(attraction|museum|viewpoint|gallery|zoo)$"]["name"];'
            f'nwr(around:{int(radius_km * 1000)},{lat},{lon})["historic"]["wikidata"];'
            f'nwr(around:{int(radius_km * 1000)},{lat},{lon})["natural"="beach"]["name"];'
            f');out center tags;')
    osm = {}
    for key, q in queries.items():
        osm[key] = {"query": q, "items": osm_items(overpass(q).get("elements", []), f"overpass:{key}"), "fetched_on": FETCHED}
        time.sleep(5)
    return {"city_id": city, "centre": [lat, lon], "radius_km": radius_km, "fetched_on": FETCHED,
            "opentripmap": {"url": OTM, "params": params, "items": otm}, "overpass": osm}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datatools.seed", description=__doc__.splitlines()[0])
    ap.add_argument("cities", nargs="+")
    ap.add_argument("--radius-km", type=float)
    ap.add_argument("--extras-only", action="store_true", help="refetch only the EXTRA_OSM block of an existing seed file")
    args = ap.parse_args(argv)
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    for city in args.cities:
        data = (refresh_extras(city) if args.extras_only
                else seed(city, args.radius_km or RADIUS_KM.get(city, DEFAULT_RADIUS_KM)))
        (SEED_DIR / f"{city}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(city, "opentripmap", len(data["opentripmap"]["items"]),
              {k: len(v["items"]) for k, v in data["overpass"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
