"""Build data/curated/hotels.csv (T10).

    python -m datatools.curation.hotels

Inputs (all in data/raw/hotels/):
- booking_observations.csv: prices seen on Booking.com city pages (USD, no dates selected).
- booking_hotel_pages.csv: coordinates read from each hotel's Booking.com page.
- booking_search_2026-11-18.csv: price-sorted searches (INR, 18-19 Nov 2026, 2 adults, 1 room)
  used to fill thin tiers.

Rules:
- price in INR = round(USD x rate); tier = first band containing the price, in order budget, mid, premium.
- candidates per tier: city-page '1 night, 2 adults' prices, then city-page 'per night' prices,
  then search results by price; dorm beds, multi-room offers, entire apartments and women-only
  properties are skipped.
- a hotel must have coordinates and lie within 25 km of the city centre.
- keep up to 3 per tier; a tier with fewer than 3 records why (001 Spec 5.6).
"""

import re

from datatools import rules
from datatools.curation.common import (CURATED, RAW, USD_INR, USD_INR_FETCHED, USD_INR_SRC, haversine_km, latest,
                                       read_csv, round_half_up, write_csv)

H = RAW / "hotels"
BOOKING = "https://www.booking.com/hotel/in/"
PER_TIER = 3
SKIP_UNIT = re.compile(r"\b(bed in|dormitory|dorm|entire apartment)\b|\d+\s*×", re.I)
SKIP_NAME = re.compile(r"\bwomen\b", re.I)  # women-only properties cannot host a 2-adult trip


def tier_of(inr: int) -> str | None:
    return next((t for t in rules.HOTEL_TIERS if rules.PRICE_BANDS[t][0] <= inr <= rules.PRICE_BANDS[t][1]), None)


def main() -> None:
    centres = {r["city_id"]: (float(r["lat"]), float(r["lon"])) for r in read_csv(CURATED / "cities.csv")}
    pages = {(r["city_id"], r["name"]): r for r in read_csv(H / "booking_hotel_pages.csv")}
    shared = {}
    for r in pages.values():
        if r["lat"]:
            shared.setdefault((r["lat"], r["lon"]), []).append(r["name"])

    cands: dict[tuple[str, str], list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    obs = read_csv(H / "booking_observations.csv")
    obs.sort(key=lambda o: o["basis"] != "1 night, 2 adults")  # stable: page order within each basis
    for o in obs:
        key = (o["city_id"], o["name"])
        if key in seen:
            continue
        seen.add(key)
        inr = round_half_up(float(o["usd"]) * USD_INR)
        t = tier_of(inr)
        page = pages.get(key)
        if not t:
            continue
        cands.setdefault((o["city_id"], t), []).append({
            "name": o["name"], "price": inr, "page": page,
            "price_src": f"price: {o['page_url']} USD {o['usd']} ({o['basis']}; no dates selected) x {USD_INR_SRC}",
            "dates": [o["observed_on"], USD_INR_FETCHED],
        })
    search = sorted(read_csv(H / "booking_search_2026-11-18.csv"), key=lambda r: int(r["price_inr"]))
    for r in search:
        key = (r["city_id"], r["name"])
        if key in seen or SKIP_UNIT.search(r["unit"]) or SKIP_NAME.search(r["name"]):
            continue
        seen.add(key)
        inr = int(r["price_inr"])
        t = tier_of(inr)
        if not t:
            continue
        page = {"slug": r["slug"], "lat": r["lat"], "lon": r["lon"], "fetched_on": r["fetched_on"]}
        cands.setdefault((r["city_id"], t), []).append({
            "name": r["name"], "price": inr, "page": page,
            "price_src": f"price: {r['search_url']} Rs {inr} for 1 night 18-19 Nov 2026, 2 adults, unit '{r['unit']}'",
            "dates": [r["fetched_on"]],
        })

    out, report = [], []
    for city in rules.CITY_CODES:
        n = 1
        for tier in rules.HOTEL_TIERS:
            picked, rejected = [], []
            for c in cands.get((city, tier), []):
                p = c["page"]
                if not p or not p["lat"]:
                    rejected.append("no coordinates")
                    continue
                km = haversine_km(float(p["lat"]), float(p["lon"]), *centres[city])
                if km > rules.HOTEL_MAX_KM_FROM_CENTRE:
                    rejected.append(f"{km:.0f} km from centre")
                    continue
                picked.append((c, p, km))
                if len(picked) == PER_TIER:
                    break
            note = "" if len(picked) >= PER_TIER else \
                f" | tier has {len(picked)}: no more listings found in this band within 25 km of the centre (001 Spec 5.6)"
            report.append(f"{city} {tier}: {len(picked)} kept from {len(cands.get((city, tier), []))} candidates")
            for c, p, km in picked:
                warn = ""
                others = [x for x in shared.get((p["lat"], p["lon"]), []) if x != c["name"]]
                if others:
                    warn = " | CHECK: Booking.com shows the same coordinates for " + "; ".join(others)
                src = (f"{c['price_src']} | coords: {BOOKING}{p['slug']}.html (data-atlas-latlng, "
                       f"{km:.1f} km from centre){warn}{note}")
                out.append([f"{city}-H-{n:02d}", city, c["name"], tier, f"{float(p['lat']):.5f}", f"{float(p['lon']):.5f}",
                            c["price"], src, latest(*c["dates"], p["fetched_on"])])
                n += 1
    write_csv(CURATED / "hotels.csv",
              ["hotel_id", "city_id", "name", "tier", "lat", "lon", "price_per_room_night", "source", "checked_on"], out)
    print("\n".join(r for r in report if not r.split(": ")[1].startswith("3 ")))
    print(f"{len(out)} hotels")


if __name__ == "__main__":
    main()
