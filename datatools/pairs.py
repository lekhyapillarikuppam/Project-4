"""Build data/curated/city_pairs.csv (001 Spec §5.3, T12).

    python -m datatools.pairs [--offline]

For each of the 105 unordered city pairs:
- road_km: OpenRouteService driving distance between the two bus hubs (one 15 x 15 matrix).
- rail: erail.in direct trains between the two train hubs. If any run, rail_km and train_minutes
  are the medians over those trains (published, not approximate). Otherwise a train with one change
  at another of the 15 train hubs counts as available, with rail_km = road_km and the fallback
  formula for train_minutes (both flagged approximate).
- air_km: great-circle distance between the flight hubs. A flight is available when one airport's
  Wikipedia "Airlines and destinations" list names the other (direct) or both name a third of the
  15 airports (one stop), and air_km >= 300. flight_minutes always uses the fallback formula
  (+120 for one stop), flagged approximate.
- bus: available when both cities have a bus hub and road_km <= 1,000; bus_minutes uses the fallback formula.

Every lookup is saved under data/raw/pairs/. --offline rebuilds from those files only.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from itertools import combinations
from pathlib import Path

import requests

from datatools import rules
from datatools.geo import haversine_km, matrix
from datatools.models import fallback_minutes

ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "data" / "curated"
RAW = ROOT / "data" / "raw" / "pairs"
ERAIL = "https://erail.in/rail/getTrains.aspx?Station_From={a}&Station_To={b}&DataSource=0&Language=0&Cache=true"
WIKI_API = "https://en.wikipedia.org/w/api.php"
UA_BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"}
UA_BOT = {"User-Agent": "Tripwise-UMC301-student-project (data curation)"}
FETCHED = "2026-10-23"


def load_hubs() -> dict[str, dict[str, dict]]:
    import csv
    hubs: dict[str, dict[str, dict]] = {}
    with open(CURATED / rules.HUBS_FILE, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            hubs.setdefault(r["city_id"], {})[r["mode"]] = r
    return hubs


# --- rail ----------------------------------------------------------------------

def erail_trains(a_code: str, b_code: str, offline: bool) -> list[dict]:
    path = RAW / "erail" / f"{a_code}_{b_code}.txt"
    if not path.exists():
        if offline:
            raise FileNotFoundError(path)
        text = requests.get(ERAIL.format(a=a_code, b=b_code), headers=UA_BROWSER, timeout=60).text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        time.sleep(1.0)
    trains = []
    for rec in path.read_text(encoding="utf-8").split("^")[1:]:
        f = rec.split("~")
        if len(f) < 40 or not re.fullmatch(r"\d+\.\d\d", f[12]) or not f[39].isdigit():
            continue
        h, m = f[12].split(".")
        trains.append({"number": f[0], "name": f[1], "from": f[7], "to": f[9],
                       "minutes": int(h) * 60 + int(m), "km": int(f[39])})
    return trains


# --- flights -------------------------------------------------------------------

def _wiki_get(params: dict) -> dict:
    for attempt in range(5):
        r = requests.get(WIKI_API, params=params, headers=UA_BOT, timeout=60)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Wikipedia API failed for {params}")


def wiki_airport(title: str, offline: bool) -> dict:
    """Canonical title, its redirect titles and the passenger destinations wikitext of an airport article."""
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", title)
    path = RAW / "wiki_airports" / f"{safe}.json"
    if not path.exists():
        if offline:
            raise FileNotFoundError(path)
        parse = _wiki_get({"action": "parse", "page": title, "prop": "wikitext", "redirects": 1,
                           "format": "json", "formatversion": 2})
        canon = parse["parse"]["title"]
        red = _wiki_get({"action": "query", "titles": canon, "prop": "redirects", "rdlimit": "max",
                         "format": "json", "formatversion": 2})
        redirects = [r["title"] for p in red["query"]["pages"] for r in p.get("redirects", [])]
        data = {"requested": title, "title": canon, "redirects": redirects, "wikitext": parse["parse"]["wikitext"],
                "url": f"https://en.wikipedia.org/wiki/{canon.replace(' ', '_')}", "fetched_on": FETCHED}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.5)
    return json.loads(path.read_text(encoding="utf-8"))


def passenger_destinations(wikitext: str) -> str:
    i = wikitext.find("Airlines and destinations")
    if i < 0:
        return ""
    rest = wikitext[i:]
    end = re.search(r"\n==[^=]", rest[30:])
    section = rest[: end.start() + 30] if end else rest
    cargo = re.search(r"\n===\s*Cargo", section, re.I)
    return section[: cargo.start()] if cargo else section


def direct_flights(airports: dict[str, dict]) -> dict[str, set[str]]:
    """city -> cities whose airport its passenger destination list links to."""
    names = {c: {a["title"], *a["redirects"]} for c, a in airports.items()}
    out = {c: set() for c in airports}
    for c, a in airports.items():
        links = {m.strip().replace("_", " ") for m in re.findall(r"\[\[([^\]|#]+)", passenger_destinations(a["wikitext"]))}
        for other, titles in names.items():
            if other != c and links & titles:
                out[c].add(other)
    return out


# --- build -----------------------------------------------------------------------

def build(offline: bool) -> None:
    hubs = load_hubs()
    cities = list(rules.CITY_CODES)

    bus_cities = [c for c in cities if "bus" in hubs[c]]
    pts = [(float(hubs[c]["bus"]["lat"]), float(hubs[c]["bus"]["lon"])) for c in bus_cities]
    if offline:
        from datatools import geo
        geo._key = lambda: (_ for _ in ()).throw(RuntimeError("offline: ORS matrix not cached"))
    road_km, _ = matrix(pts)
    road = {(a, b): road_km[i][j] for i, a in enumerate(bus_cities) for j, b in enumerate(bus_cities)}
    (RAW / "ors_bus_matrix.json").parent.mkdir(parents=True, exist_ok=True)
    (RAW / "ors_bus_matrix.json").write_text(json.dumps(
        {"profile": "driving-car", "fetched_on": FETCHED, "nodes": bus_cities, "points_lat_lon": pts,
         "km": [[round(x, 1) for x in row] for row in road_km]}, indent=1), encoding="utf-8")

    rail: dict[tuple[str, str], list[dict]] = {}
    for a, b in combinations(sorted(cities), 2):
        if "train" in hubs[a] and "train" in hubs[b]:
            rail[(a, b)] = erail_trains(hubs[a]["train"]["hub_code"], hubs[b]["train"]["hub_code"], offline)
    direct_rail = {k for k, v in rail.items() if v}

    def has_direct_rail(x: str, y: str) -> bool:
        return tuple(sorted((x, y))) in direct_rail

    airports = {c: wiki_airport(hubs[c]["flight"]["source"].split("coords: ")[1].split(" ")[0].rsplit("/", 1)[1].replace("_", " "), offline)
                for c in cities if "flight" in hubs[c]}
    direct_air = direct_flights(airports)

    def flies(x: str, y: str) -> bool:
        return y in direct_air.get(x, set()) or x in direct_air.get(y, set())

    rows = []
    for a, b in combinations(sorted(cities), 2):
        src = []
        rkm = road.get((a, b))
        road_km_v = round(rkm, 1) if rkm is not None else None
        src.append("road: ORS driving-car between bus hubs (data/raw/pairs/ors_bus_matrix.json)")

        trains = rail.get((a, b), [])
        if trains:
            rail_km = float(statistics.median(t["km"] for t in trains))
            train_min = round(statistics.median(t["minutes"] for t in trains))
            train_ok, rail_approx, train_approx = True, False, False
            src.append(f"rail: {len(trains)} direct trains on erail.in, median distance and duration "
                       f"(data/raw/pairs/erail/{hubs[a]['train']['hub_code']}_{hubs[b]['train']['hub_code']}.txt)")
        else:
            via = [x for x in cities if x not in (a, b) and "train" in hubs[x] and has_direct_rail(a, x) and has_direct_rail(x, b)]
            train_ok = bool(via) and (a, b) in rail
            rail_km, rail_approx = road_km_v, True
            train_min = fallback_minutes(rail_km, rules.TRAIN_FALLBACK) if train_ok else None
            train_approx = train_ok
            src.append(f"rail: no direct train on erail.in; one change via {','.join(via)}" if train_ok
                       else "rail: no direct or one-change train among the 15 hubs on erail.in" if (a, b) in rail
                       else "rail: a city has no train hub")

        air_km = None
        flight_ok, one_stop = False, False
        if a in airports and b in airports:
            fa, fb = hubs[a]["flight"], hubs[b]["flight"]
            air_km = round(haversine_km(float(fa["lat"]), float(fa["lon"]), float(fb["lat"]), float(fb["lon"])), 1)
            if flies(a, b):
                flight_ok = air_km >= rules.FLIGHT_MIN_AIR_KM
                src.append("flight: direct route in Wikipedia destination lists")
            else:
                stops = [x for x in airports if x not in (a, b) and flies(a, x) and flies(x, b)]
                one_stop = bool(stops)
                flight_ok = one_stop and air_km >= rules.FLIGHT_MIN_AIR_KM
                src.append(f"flight: one stop via {','.join(stops)}" if stops else "flight: no direct or one-stop route among the 15 airports")
            src.append("(data/raw/pairs/wiki_airports/)")
        flight_min = None
        if flight_ok:
            flight_min = fallback_minutes(air_km, rules.FLIGHT_FALLBACK) + (rules.FLIGHT_ONE_STOP_EXTRA_MIN if one_stop else 0)

        bus_ok = road_km_v is not None and road_km_v <= rules.BUS_MAX_ROAD_KM
        bus_min = fallback_minutes(road_km_v, rules.BUS_FALLBACK) if bus_ok else None

        rows.append([a, b, f"{road_km_v:.1f}", f"{rail_km:.1f}", "" if air_km is None else f"{air_km:.1f}",
                     str(train_ok).lower(), str(bus_ok).lower(), str(flight_ok).lower(),
                     train_min or "", bus_min or "", flight_min or "",
                     str(rail_approx).lower(), str(train_approx).lower(), str(bus_ok).lower(), str(flight_ok).lower(),
                     " | ".join(src), FETCHED])

    import csv
    with open(CURATED / rules.PAIRS_FILE, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["city_a", "city_b", "road_km", "rail_km", "air_km", "train_available", "bus_available",
                    "flight_available", "train_minutes", "bus_minutes", "flight_minutes", "rail_km_approx",
                    "train_minutes_approx", "bus_minutes_approx", "flight_minutes_approx", "source", "checked_on"])
        w.writerows(rows)
    n = len(rows)
    print(f"{n} pairs; train {sum(r[5] == 'true' for r in rows)} (direct {len(direct_rail)}), "
          f"bus {sum(r[6] == 'true' for r in rows)}, flight {sum(r[7] == 'true' for r in rows)}; "
          f"no mode {sum(r[5] == r[6] == r[7] == 'false' for r in rows)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m datatools.pairs", description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use only the saved lookups in data/raw/pairs/")
    build(parser.parse_args(argv).offline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
