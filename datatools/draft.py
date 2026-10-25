"""Turn seed candidates into a ranked draft list (001 Spec §5.5, §6.2, T14).

    python -m datatools.draft <CITY> [<CITY> ...]

For each city it reads data/raw/seed/<CITY>.json and writes data/raw/attractions/<CITY>_draft.csv:
one row per distinct place, ranked by popularity, with suggested tags and place type. Lookups are
saved under data/raw/wiki/<CITY>/:
- wikidata.json: Wikidata id -> English Wikipedia title,
- pageviews.json: monthly pageviews over the 12 complete months PAGEVIEW_START..PAGEVIEW_END, fetched
  for the PAGEVIEW_TOP_N candidates with the highest OpenTripMap rate (cached titles are always used;
  datatools.curation.attractions fetches any selected title still missing),
- summaries.json: Wikipedia page summaries, used for tag keywords.

The draft is not the dataset: data/raw/attractions/<CITY>_selection.csv records which candidates
were chosen and how they were classified, and datatools.curation.attractions builds the final file.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

from datatools.geo import haversine_km

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
# Wikimedia User-Agent policy: identify the tool and a contact.
UA = {"User-Agent": "Tripwise/1.0 (UMC301 student project; lekhya.pillarikuppam@gmail.com)"}
PAGEVIEW_START, PAGEVIEW_END = "2025100100", "2026093000"   # 12 complete months before 2026-10-23
PAGEVIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
             "{title}/monthly/" + PAGEVIEW_START + "/" + PAGEVIEW_END)
SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
WIKIDATA = "https://www.wikidata.org/w/api.php"
SUMMARY_TOP_N = 120
PAGEVIEW_TOP_N = 80   # pageviews are fetched for the city's top candidates by OpenTripMap rate only

# OpenTripMap kinds / OSM tags -> place type, first match wins (001 Spec §5.5 types and aliases).
TYPE_RULES = [
    ("beach", r"\bbeaches\b|natural=beach"), ("museum", r"museums|galler|zoos|aquariums"), ("ghat", r"\bghat"),
    ("temple", r"religion|temples|churches|mosques|gurdwara|place_of_worship"),
    ("market", r"marketplace|shop=mall|bazaar|markets"), ("activity", r"amusements|sport|climbing|diving|water_parks|theatres|nightclub|pub|bar\b"),
    ("garden", r"gardens_and_parks|leisure=park|leisure=garden"),
    ("viewpoint", r"view_points|natural|lakes|waterfalls|nature_reserves|urban_environment"),
    ("fort", r"fortifications|palaces|castles"),
    ("monument", r"historic|archaeology|monuments|architecture|towers|bridges"),
]
# Keywords in kinds, OSM tags or the Wikipedia summary -> interest tag (section 4 values only).
TAG_RULES = [
    ("spiritual", r"religion|temple|mosque|church|gurdwara|shrine|pilgrim|ghat|aarti|monastery|place_of_worship|dargah"),
    ("history", r"historic|archaeolog|fort|palace|tomb|mausoleum|monument|ruins|heritage|ancient|medieval|century|mughal|colonial"),
    ("culture", r"museum|gallery|theatre|cultural|art\b|arts|architecture|crafts|observatory"),
    ("nature", r"natural|garden|park|lake|waterfall|beach|hill|forest|wildlife|botanical|river|nature_reserve|view_points"),
    ("shopping", r"market|bazaar|shopping|mall|shop=|handicraft"),
    ("food", r"food|street food|cuisine|eateries|restaurants|sweets|chaat|culinary"),
    ("relaxation", r"beach|garden|park|lake|promenade|spa\b"),
    ("adventure", r"trek|rafting|adventure|climbing|diving|water sports|paragliding|zip|amusements"),
    ("nightlife", r"nightlife|nightclub|\bpub\b|\bbar\b|clubs|night market|party"),
]
EXCLUDE_KINDS = re.compile(r"historic_settlements|cemeteries|industrial_facilities")


def _get(url: str, params: dict | None = None) -> requests.Response:
    for attempt in range(8):
        r = requests.get(url, params=params, headers=UA, timeout=60)
        if r.status_code in (200, 404):
            return r
        time.sleep(15 * (attempt + 1) if r.status_code == 429 else 3 * (attempt + 1))
    r.raise_for_status()
    return r


def load_cache(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for attempt in range(5):   # Windows can briefly lock a file that was just written (Errno 22/13)
        try:
            tmp.replace(path)
            return
        except OSError:
            time.sleep(0.5 * (attempt + 1))
    tmp.replace(path)


def wiki_titles(qids: list[str], cache_path: Path) -> dict[str, str | None]:
    cache = load_cache(cache_path)
    todo = [q for q in qids if q not in cache]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        d = _get(WIKIDATA, {"action": "wbgetentities", "ids": "|".join(batch), "props": "sitelinks",
                            "sitefilter": "enwiki", "format": "json"}).json()
        for q in batch:
            links = d.get("entities", {}).get(q, {}).get("sitelinks", {})
            cache[q] = links.get("enwiki", {}).get("title")
        save_cache(cache_path, cache)
        time.sleep(0.5)
    return cache


def pageviews(titles: list[str], cache_path: Path) -> dict[str, int | None]:
    """Title -> 12-month views. Fetch dates go to <cache>_fetched.json (titles cached before it existed have none)."""
    cache = load_cache(cache_path)
    dates_path = fetched_path(cache_path)
    dates = load_cache(dates_path)
    for t in titles:
        if t in cache:
            continue
        r = _get(PAGEVIEWS.format(title=quote(t.replace(" ", "_"), safe="")))
        cache[t] = sum(i["views"] for i in r.json().get("items", [])) if r.status_code == 200 else None
        dates[t] = time.strftime("%Y-%m-%d")
        save_cache(cache_path, cache)
        save_cache(dates_path, dates)
        time.sleep(0.2)   # Wikimedia rate limits bursts (HTTP 429)
    return cache


def fetched_path(cache_path: Path) -> Path:
    return cache_path.with_name(cache_path.stem + "_fetched.json")


def summaries(titles: list[str], cache_path: Path) -> dict[str, dict]:
    cache = load_cache(cache_path)
    for t in titles:
        if t in cache:
            continue
        r = _get(SUMMARY.format(title=quote(t.replace(" ", "_"), safe="")))
        j = r.json() if r.status_code == 200 else {}
        cache[t] = {"description": j.get("description"), "extract": j.get("extract"),
                    "url": (j.get("content_urls") or {}).get("desktop", {}).get("page")}
        save_cache(cache_path, cache)
        time.sleep(0.2)
    return cache


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def suggest(text: str) -> tuple[str, list[str]]:
    low = text.lower()
    ptype = next((t for t, rx in TYPE_RULES if re.search(rx, low)), "monument")
    tags = [t for t, rx in TAG_RULES if re.search(rx, low)]
    return ptype, tags


def draft(city: str) -> Path:
    seed = json.loads((RAW / "seed" / f"{city}.json").read_text(encoding="utf-8"))
    clat, clon = seed["centre"]
    items = list(seed["opentripmap"]["items"])
    for block in seed["overpass"].values():
        items += block["items"]

    merged: dict[str, dict] = {}
    for it in items:
        if EXCLUDE_KINDS.search(it.get("kinds", "")):
            continue
        key = it.get("wikidata") or "name:" + norm(it["name"])
        cur = merged.get(key)
        if cur is None or it.get("rate", 0) > cur.get("rate", 0):
            merged[key] = {**(cur or {}), **it}

    wdir = RAW / "wiki" / city
    titles = wiki_titles(sorted({m["wikidata"] for m in merged.values() if m.get("wikidata")}), wdir / "wikidata.json")
    for m in merged.values():
        m["wiki_title"] = titles.get(m.get("wikidata")) if m.get("wikidata") else None
    for m in merged.values():
        m["otm_rate"] = (m["rate"] % 4 or 1) if m.get("rate") else None   # 1..3; +4 marks the heritage flag
    by_rate = sorted((m for m in merged.values() if m["wiki_title"]), key=lambda m: (m["otm_rate"] or 0, m.get("rate", 0)), reverse=True)
    pv = pageviews(sorted({m["wiki_title"] for m in by_rate[:PAGEVIEW_TOP_N]}), wdir / "pageviews.json")
    for m in merged.values():
        m["pageviews"] = pv.get(m["wiki_title"]) if m["wiki_title"] else None
        m["km"] = round(haversine_km(clat, clon, m["lat"], m["lon"]), 1)

    ranked = sorted(merged.values(), key=lambda m: (m["pageviews"] or 0, m["otm_rate"] or 0), reverse=True)
    top_titles = [m["wiki_title"] for m in ranked[:SUMMARY_TOP_N] if m["wiki_title"]]
    summ = summaries(top_titles, wdir / "summaries.json")

    out = RAW / "attractions" / f"{city}_draft.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["candidate", "name", "lat", "lon", "km", "wikidata", "wiki_title", "pageviews", "otm_rate",
                    "suggested_type", "suggested_tags", "kinds_or_osm", "description"])
        for m in ranked:
            s = summ.get(m["wiki_title"], {}) if m["wiki_title"] else {}
            osm_tags = ";".join(f"{k}={v}" for k, v in (m.get("osm_tags") or {}).items()
                                if k in ("amenity", "shop", "tourism", "historic", "natural", "leisure", "place"))
            basis = " ".join(filter(None, [m.get("kinds", ""), osm_tags, s.get("description") or "", s.get("extract") or ""]))
            ptype, tags = suggest(basis)
            w.writerow([m.get("xid") or m.get("osm"), m["name"], f"{m['lat']:.5f}", f"{m['lon']:.5f}", m["km"],
                        m.get("wikidata") or "", m["wiki_title"] or "", m["pageviews"] if m["pageviews"] is not None else "",
                        m["otm_rate"] or "", ptype, ";".join(tags), m.get("kinds") or osm_tags, (s.get("description") or "")[:100]])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datatools.draft", description=__doc__.splitlines()[0])
    ap.add_argument("cities", nargs="+")
    for city in ap.parse_args(argv).cities:
        path = draft(city)
        print(city, sum(1 for _ in open(path, encoding="utf-8")) - 1, "candidates ->", path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
