"""Find English Wikipedia articles for selected attractions that have no wiki_title.

    python -m datatools.curation.wiki_search <CITY> [<CITY> ...]

For each row of data/raw/attractions/<CITY>_selection.csv whose candidate has no wiki_title (in the
selection or the draft), it searches English Wikipedia by name (opensearch), then by "<name> <city>",
then by name with the fuzzy profile (spelling variants such as Vitthala/Vittala), and looks up each
result's coordinates and short description. Responses are cached in data/raw/wiki/<CITY>/opensearch.json
with their fetch date.

It prints the results with their distance from the attraction. A result is a clear match when its
article is about this place (not the town or area around it) and its coordinates lie within MATCH_KM,
or, for an article without coordinates, its description places it in this city. The chosen title is
entered by hand in the selection's wiki_title column, and datatools.curation.attractions fetches its
pageviews.
"""

from __future__ import annotations

import sys
import time

from datatools import draft as drafting
from datatools.curation.common import RAW, haversine_km, read_csv

API = "https://en.wikipedia.org/w/api.php"
MATCH_KM = 2.0
RESULTS = 5
CITY_NAMES = {"JAI": "Jaipur", "AGR": "Agra", "HMP": "Hampi", "MUN": "Munnar", "RSH": "Rishikesh", "DJL": "Darjeeling",
              "GOA": "Goa", "PDY": "Pondicherry", "DEL": "Delhi", "BOM": "Mumbai", "BLR": "Bangalore", "CCU": "Kolkata",
              "HYD": "Hyderabad", "VNS": "Varanasi", "MAA": "Chennai"}
FETCHED = time.strftime("%Y-%m-%d")


def lookup(query: str, cache: dict, profile: str = "") -> list[dict]:
    key = f"{query} [{profile}]" if profile else query
    if key not in cache:
        params = {"action": "opensearch", "search": query, "limit": RESULTS, "namespace": 0, "format": "json"}
        if profile:
            params["profile"] = profile
        titles = drafting._get(API, params).json()[1]
        info = []
        if titles:
            q = drafting._get(API, {"action": "query", "prop": "coordinates|description", "titles": "|".join(titles),
                                    "redirects": 1, "format": "json"}).json()["query"]
            redirect = {r["from"]: r["to"] for r in q.get("redirects", [])}
            pages = {p["title"]: p for p in q.get("pages", {}).values()}
            for t in titles:
                p = pages.get(redirect.get(t, t), {})
                c = (p.get("coordinates") or [{}])[0]
                info.append({"title": p.get("title", t), "description": p.get("description"),
                             "lat": c.get("lat"), "lon": c.get("lon")})
        cache[key] = {"fetched_on": FETCHED, "results": info}
        time.sleep(0.3)
    return cache[key]["results"]


def search(city: str) -> None:
    draft = {r["candidate"]: r for r in read_csv(RAW / "attractions" / f"{city}_draft.csv")}
    path = RAW / "wiki" / city / "opensearch.json"
    cache = drafting.load_cache(path)
    for s in read_csv(RAW / "attractions" / f"{city}_selection.csv"):
        d = draft.get(s["candidate"], {})
        if s["candidate"].startswith("activity:") or s.get("wiki_title") or d.get("wiki_title"):
            continue
        lat, lon = float(s.get("lat") or d["lat"]), float(s.get("lon") or d["lon"])
        print(f"{city} {s['candidate']} {s['name']!r}")
        for query, profile in ((s["name"], ""), (f"{s['name']} {CITY_NAMES[city]}", ""), (s["name"], "fuzzy")):
            for r in lookup(query, cache, profile):
                km = round(haversine_km(lat, lon, r["lat"], r["lon"]), 1) if r["lat"] is not None else None
                flag = "near" if km is not None and km <= MATCH_KM else ""
                print(f"    [{query}{' ~' if profile else ''}] {r['title']!r} km={km} {flag} - {r['description']}")
        drafting.save_cache(path, cache)


def main(argv: list[str] | None = None) -> int:
    for city in (argv if argv is not None else sys.argv[1:]):
        search(city)
    return 0


if __name__ == "__main__":
    sys.exit(main())
