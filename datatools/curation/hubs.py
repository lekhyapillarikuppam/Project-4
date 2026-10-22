"""Build data/curated/hubs.csv (T07).

    python -m datatools.curation.hubs

Coordinates come from Wikipedia infoboxes, Nominatim or Overpass (URL in source).
access_km / access_minutes: OpenRouteService driving-car, hub -> city centre, free-flow.
Raw responses are cached in data/raw/ors/ (git-ignored); a summary is written to
data/raw/hubs/ors_access.csv. access_cost_per_vehicle = the city's cab ride cost for
access_km under the local_transport tariff (001 Spec 5.8).
"""

import hashlib
import json
import os

import requests
from dotenv import load_dotenv

from datatools.curation.common import CURATED, RAW, ROOT, fetched_on, latest, read_csv, round_half_up, write_csv

W = "https://en.wikipedia.org/wiki/"
N = "https://nominatim.openstreetmap.org/search?format=json&limit=3&q="
NOMINATIM_FETCHED = "2026-10-22"   # data/raw/hubs/nominatim_bus.json
OVERPASS = "https://overpass-api.de/api/interpreter"
ORS = "https://api.openrouteservice.org/v2/directions/driving-car"

HUBS = [  # city, mode, name, code, lat, lon, coordinate source, note
    ("JAI", "train", "Jaipur Junction", "JP", 26.9208, 75.7866, W + "Jaipur_Junction_railway_station", ""),
    ("JAI", "bus", "Sindhi Camp Bus Stand", "", 26.92331, 75.80063, N + "Sindhi+Camp+Bus+Stand+Jaipur", ""),
    ("JAI", "flight", "Jaipur International Airport", "JAI", 26.82417, 75.81222, W + "Jaipur_International_Airport", ""),
    ("AGR", "train", "Agra Cantt", "AGC", 27.15889, 77.99056, W + "Agra_Cantonment_railway_station", ""),
    ("AGR", "bus", "Idgah Bus Stand", "", 27.16607, 77.99547, N + "Idgah+Bus+Stand+Agra", ""),
    ("AGR", "flight", "Agra Airport", "AGR", 27.16183, 77.97073, W + "Agra_Airport", "Wikipedia lists IndiGo to Bengaluru and Navi Mumbai"),
    ("HMP", "train", "Hosapete Jn", "HPT", 15.2865, 76.3867, W + "Hosapete_Junction_railway_station", "outside-city hub (spec 5.2)"),
    ("HMP", "bus", "Hosapete Bus Stand", "", 15.27519, 76.38926, N + "Hosapete+bus+station", "intercity buses via Hosapete"),
    ("HMP", "flight", "Jindal Vijaynagar Airport", "VDY", 15.1750, 76.6341, W + "Jindal_Vijaynagar_Airport",
     "chosen over Hubballi (HBX, https://en.wikipedia.org/wiki/Hubli_Airport) as nearer; Star Air lists Vidyanagar (VDY) and a Bengaluru-Vidyanagar route (https://www.starair.in/); Alliance Air site could not be checked"),
    ("MUN", "train", "Aluva", "AWY", 10.10806, 76.35611, W + "Aluva_railway_station",
     "from DMS 10 06 29 N 76 21 22 E; Munnar page: Aluva 110 km, KSRTC buses hourly to Munnar (https://en.wikipedia.org/wiki/Munnar)"),
    ("MUN", "bus", "KSRTC Bus Stand Munnar", "", 10.07288, 77.06202, N + "Munnar+KSRTC+Bus+Station", ""),
    ("MUN", "flight", "Cochin International Airport", "COK", 10.15333, 76.38816, W + "Cochin_International_Airport", "Munnar page: nearest airport, 110 km"),
    ("RSH", "train", "Yog Nagari Rishikesh", "YNRK", 30.10996, 78.27808, W + "Yog_Nagari_Rishikesh_railway_station", "long-distance trains listed on the page"),
    ("RSH", "bus", "ISBT Rishikesh", "", 30.11294, 78.29572, N + "ISBT+Rishikesh", ""),
    ("RSH", "flight", "Dehradun Airport (Jolly Grant)", "DED", 30.18972, 78.18028, W + "Dehradun_Airport", "outside-city hub (spec 5.2)"),
    ("DJL", "train", "New Jalpaiguri Jn", "NJP", 26.68250, 88.44389, W + "New_Jalpaiguri_Junction_railway_station", "outside-city hub (spec 5.2)"),
    ("DJL", "bus", "Tenzing Norgay Bus Terminus Siliguri", "", 26.72497, 88.41488, N + "Tenzing+Norgay+Bus+Terminus", "intercity buses terminate in Siliguri"),
    ("DJL", "flight", "Bagdogra Airport", "IXB", 26.68111, 88.32861, W + "Bagdogra_Airport", "outside-city hub (spec 5.2)"),
    ("GOA", "train", "Madgaon Jn", "MAO", 15.2677, 73.9711, W + "Madgaon_Junction_railway_station", ""),
    ("GOA", "bus", "Kadamba Bus Terminus Panaji", "", 15.49532, 73.83703, N + "Kadamba+Bus+Stand+Panaji", ""),
    ("GOA", "flight", "Goa International Airport (Dabolim)", "GOI", 15.38083, 73.83139, W + "Dabolim_Airport", ""),
    ("PDY", "train", "Puducherry", "PDY", 11.9250, 79.8281, W + "Puducherry_railway_station", ""),
    ("PDY", "bus", "Puducherry New Bus Stand", "", 11.93314, 79.81594, N + "Puducherry+New+Bus+Stand", ""),
    ("PDY", "flight", "Puducherry Airport", "PNY", 11.96667, 79.81444, W + "Puducherry_Airport",
     "Wikipedia lists IndiGo to Bengaluru, Hyderabad and Rajahmundry, and IndiGo added Puducherry-Bengaluru services (https://newsonair.gov.in/puducherry-airport-expands-connectivity-with-new-indigo-bengaluru-flight-services/), so used instead of Chennai (spec 5.2)"),
    ("DEL", "train", "New Delhi", "NDLS", 28.6428, 77.21908, W + "New_Delhi_railway_station", ""),
    ("DEL", "bus", "Maharana Pratap ISBT (Kashmere Gate)", "", 28.66864, 77.22947, W + "Kashmere_Gate_ISBT", ""),
    ("DEL", "flight", "Indira Gandhi International Airport", "DEL", 28.56861, 77.11222, W + "Indira_Gandhi_International_Airport", ""),
    ("BOM", "train", "Chhatrapati Shivaji Maharaj Terminus", "CSMT", 18.93985, 72.83544, W + "Chhatrapati_Shivaji_Maharaj_Terminus", ""),
    ("BOM", "bus", "Mumbai Central Bus Station (MSRTC)", "", 18.96933, 72.82206, OVERPASS,
     "OSM way 49685673, operator MSRTC, next to Mumbai Central station (https://en.wikipedia.org/wiki/Mumbai_Central_railway_station); response in data/raw/hubs/overpass_bom_bus.json"),
    ("BOM", "flight", "Chhatrapati Shivaji Maharaj International Airport", "BOM", 19.08861, 72.86806, W + "Chhatrapati_Shivaji_Maharaj_International_Airport", ""),
    ("BLR", "train", "KSR Bengaluru", "SBC", 12.97833, 77.56944, W + "KSR_Bengaluru_railway_station", ""),
    ("BLR", "bus", "Kempegowda Bus Station (Majestic)", "", 12.97679, 77.57260, W + "Kempegowda_Bus_Station", ""),
    ("BLR", "flight", "Kempegowda International Airport", "BLR", 13.19889, 77.70556, W + "Kempegowda_International_Airport", ""),
    ("CCU", "train", "Howrah", "HWH", 22.5829, 88.3428, W + "Howrah_railway_station", ""),
    ("CCU", "bus", "Esplanade Bus Terminus", "", 22.56256, 88.34980, N + "Esplanade+Bus+Terminus+Kolkata", ""),
    ("CCU", "flight", "Netaji Subhas Chandra Bose International Airport", "CCU", 22.65472, 88.44667, W + "Netaji_Subhas_Chandra_Bose_International_Airport", ""),
    ("HYD", "train", "Secunderabad Jn", "SC", 17.4337, 78.5016, W + "Secunderabad_Junction_railway_station", ""),
    ("HYD", "bus", "Mahatma Gandhi Bus Station", "", 17.37806, 78.48389, W + "Mahatma_Gandhi_Bus_Station", "from DMS 17 22 41 N 78 29 02 E"),
    ("HYD", "flight", "Rajiv Gandhi International Airport", "HYD", 17.23000, 78.43194, W + "Rajiv_Gandhi_International_Airport", ""),
    ("VNS", "train", "Varanasi Jn", "BSB", 25.32694, 82.98639, W + "Varanasi_Junction_railway_station", ""),
    ("VNS", "bus", "Varanasi Bus Stand (Cantt)", "", 25.32875, 82.99012, N + "Varanasi+Cantt+Bus+Stand", "OSM tags it bus_stop"),
    ("VNS", "flight", "Lal Bahadur Shastri International Airport", "VNS", 25.45222, 82.85944, W + "Lal_Bahadur_Shastri_International_Airport", ""),
    ("MAA", "train", "Chennai Central", "MAS", 13.0825, 80.2750, W + "Chennai_Central_railway_station", ""),
    ("MAA", "bus", "Chennai Mofussil Bus Terminus (CMBT, Koyambedu)", "", 13.06745, 80.20566, W + "Chennai_Mofussil_Bus_Terminus",
     "APPROX single hub: westbound buses use CMBT, southbound use Kilambakkam (KCBT), northbound use Madhavaram "
     "(https://www.thenewsminute.com/tamil-nadu/chennais-new-bus-terminus-in-kilambakkam-here-is-all-you-need-to-know)"),
    ("MAA", "flight", "Chennai International Airport", "MAA", 12.98222, 80.16361, W + "Chennai_International_Airport", ""),
]


def route(key: str, a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """Driving distance (km) and free-flow time (min) from a to b. Points may snap up to 2 km to a road."""
    start, end = f"{a[1]},{a[0]}", f"{b[1]},{b[0]}"
    cache = RAW / "ors" / f"dir_{hashlib.md5((start + end).encode()).hexdigest()[:12]}.json"
    if cache.exists():
        d = json.loads(cache.read_text())
    else:
        r = requests.post(ORS + "/geojson", headers={"Authorization": key},
                          json={"coordinates": [[a[1], a[0]], [b[1], b[0]]], "radiuses": [2000, 2000]}, timeout=60)
        d = r.json()
        if "features" not in d:
            raise RuntimeError(f"ORS error for {start} -> {end}: {d.get('error')}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(d))
    s = d["features"][0]["properties"]["summary"]
    return s.get("distance", 0) / 1000, s.get("duration", 0) / 60


def main() -> None:
    load_dotenv(ROOT / ".env")
    key = os.environ["ORS_API_KEY"]
    dates = fetched_on()
    centres = {r["city_id"]: (float(r["lat"]), float(r["lon"])) for r in read_csv(CURATED / "cities.csv")}
    cab = {r["city_id"]: r for r in read_csv(CURATED / "local_transport.csv") if r["mode"] == "cab"}
    ors_date = "2026-10-23"
    rows, summary = [], []
    for c, m, name, code, lat, lon, csrc, note in HUBS:
        km, mins = route(key, (lat, lon), centres[c])
        km = round(km, 1)
        mins = max(1, round(mins)) if km > 0 else 0
        t = cab[c]
        cost = round_half_up(int(t["min_fare"]) + float(t["per_km"]) * max(0.0, km - float(t["min_km"])))
        coord_date = NOMINATIM_FETCHED if csrc.startswith(N) else dates[csrc]
        src = [f"coords: {csrc}",
               f"access: ORS driving-car free-flow, hub to centre {centres[c][0]},{centres[c][1]} (data/raw/hubs/ors_access.csv)",
               f"cost: cab ride cost under local_transport.csv {c} cab tariff ({t['min_fare']} for {t['min_km']} km + {t['per_km']}/km"
               + (", APPROX tariff" if t["approx"] == "true" else "") + ")"]
        if note:
            src.append(note)
        rows.append([c, m, name, code, f"{lat}", f"{lon}", f"{km:.1f}", mins, cost, " | ".join(src),
                     latest(coord_date, ors_date, t["checked_on"])])
        summary.append([c, m, f"{lat},{lon}", f"{centres[c][0]},{centres[c][1]}", f"{km:.1f}", mins, ors_date])
    write_csv(CURATED / "hubs.csv", ["city_id", "mode", "hub_name", "hub_code", "lat", "lon", "access_km", "access_minutes",
                                     "access_cost_per_vehicle", "source", "checked_on"], rows)
    write_csv(RAW / "hubs" / "ors_access.csv", ["city_id", "mode", "hub", "centre", "km", "minutes_free_flow", "fetched_on"], summary)
    for r in rows:
        print(r[0], r[1], r[6], r[7], r[8])


if __name__ == "__main__":
    main()
