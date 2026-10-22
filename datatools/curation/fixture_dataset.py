"""Generate the fake 2-city fixture dataset used by the validator tests (DATA-AT-02).

    python -m datatools.curation.fixture_dataset [OUT_DIR]
"""
import csv, json, math, sys
from pathlib import Path

out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "valid")
out.mkdir(parents=True, exist_ok=True)
(out / "attractions").mkdir(exist_ok=True); (out / "matrices").mkdir(exist_ok=True)
SRC, CHK = "test fixture (not real data)", "2026-10-01"
centres = {"JAI": (26.91240, 75.78730), "AGR": (27.17670, 78.00810)}

def w(name, header, rows):
    with open(out / name, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, lineterminator="\n"); wr.writerow(header); wr.writerows(rows)

(out / "VERSION").write_text("version=1.0\ncompiled=2026-11\n", encoding="utf-8")
w("cities.csv", ["city_id","name","lat","lon","traffic_factor","food_multiplier","source","checked_on"],
  [["JAI","Jaipur",*centres["JAI"],1.2,1.0,SRC,CHK],["AGR","Agra",*centres["AGR"],1.2,0.9,SRC,CHK]])

def off(city, dlat, dlon):
    la, lo = centres[city]; return f"{la+dlat:.5f}", f"{lo+dlon:.5f}"

hubs = {"JAI": [("train","Fixture Jn","FXJ",0.010,0.010),("bus","Fixture Bus Stand","",-0.010,0.010),("flight","Fixture Airport","FXA",-0.080,0.040)],
        "AGR": [("train","Fixture Cantt","FXC",0.012,-0.010),("bus","Fixture ISBT","",0.020,0.020)]}
rows = []
for c, hs in hubs.items():
    for mode, name, code, dl, dn in hs:
        km = round(math.hypot(dl, dn) * 111 * 1.3, 1)
        rows.append([c, mode, name, code, *off(c, dl, dn), km, round(km*3)+5, 50+round(km*20), SRC, CHK])
w("hubs.csv", ["city_id","mode","hub_name","hub_code","lat","lon","access_km","access_minutes","access_cost_per_vehicle","source","checked_on"], rows)

w("city_pairs.csv", ["city_a","city_b","road_km","rail_km","air_km","train_available","bus_available","flight_available",
   "train_minutes","bus_minutes","flight_minutes","rail_km_approx","train_minutes_approx","bus_minutes_approx","flight_minutes_approx","source","checked_on"],
  [["AGR","JAI",240.0,240.0,"","true","true","false",322,350,"","true","true","true","false",SRC,CHK]])

w("fare_rates.csv", ["mode","class","base_fare","per_km","min_fare","comfort_value","source","checked_on"],
  [["train","SL",20,0.5,100,0.2,SRC,CHK],["train","3A",40,1.3,300,0.6,SRC,CHK],["train","2A",50,1.9,500,0.8,SRC,CHK],
["bus","ACS",20,2.2,400,0.5,SRC,CHK],["flight","Y",2000,4.5,2500,0.9,SRC,CHK]])

tagsets = ["history;culture","culture;history","history","culture","shopping;food","food","nature;relaxation","spiritual;culture"]
nodes = {}
for c in centres:
    rows = []
    for i in range(1, 27):
        ang = i * 0.7; r = 0.01 + 0.004 * i
        lat, lon = off(c, r * math.sin(ang), r * math.cos(ang))
        tags = "shopping" if i == 26 else tagsets[(i-1) % len(tagsets)]
        fee = 0 if i % 5 == 0 else 50 * (1 + i % 4)
        rows.append([f"{c}-A-{i:02d}", c, f"Fixture Site {c} {i:02d}", lat, lon, 60 + 10*(i%6),
                     "09:00" if i % 7 else "00:00", "18:00" if i % 7 else "23:59", "0" if i % 9 == 0 else "",
                     fee, tags, f"{3.5 + (i%15)/10:.1f}", "true" if i % 2 else "false",
                     ["low","medium","high"][i%3], "false", SRC, CHK])
    w(f"attractions/{c}.csv", ["attraction_id","city_id","name","lat","lon","visit_minutes","open_time","close_time",
       "closed_weekdays","entry_fee","tags","rating","outdoor","crowd_level","fixed_slot","source","checked_on"], rows)
    nodes[c] = [(r[0], float(r[3]), float(r[4])) for r in rows]

rows = []
prices = {"budget": [900, 1400, 2100], "mid": [2600, 3800, 5200], "premium": [6500, 9000, 14000]}
for c in centres:
    n = 1; hl = []
    for tier, ps in prices.items():
        for k, p in enumerate(ps):
            lat, lon = off(c, 0.03 * (k - 1), 0.025 * (n % 4) - 0.04)
            hid = f"{c}-H-{n:02d}"
            rows.append([hid, c, f"Fixture Hotel {c} {n:02d}", tier, lat, lon, p, SRC, CHK])
            hl.append((hid, float(lat), float(lon))); n += 1
    nodes[c] = hl + nodes[c]
w("hotels.csv", ["hotel_id","city_id","name","tier","lat","lon","price_per_room_night","source","checked_on"], rows)

w("food.csv", ["comfort","base_per_person_per_day","source","checked_on"],
  [["budget",400,SRC,CHK],["mid",800,SRC,CHK],["premium",1600,SRC,CHK]])
w("local_transport.csv", ["city_id","mode","min_fare","min_km","per_km","capacity","approx","source","checked_on"],
  [[c, m, mf, mk, k, cap, "false", SRC, CHK] for c in centres for m, mf, mk, k, cap in (("auto",30,1.5,15.0,3),("cab",100,4.0,24.0,4))])

def hav(a, b):
    p1, p2 = math.radians(a[1]), math.radians(b[1]); dp = p2-p1; dl = math.radians(b[2]-a[2])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*6371*math.asin(math.sqrt(h))

for c, hs in hubs.items():
    ns = nodes[c] + [(f"{c}-HUB-{m}", float(off(c, dl, dn)[0]), float(off(c, dl, dn)[1])) for m, _, _, dl, dn in hs]
    km = [[0.0 if i == j else max(0.1, round(hav(a, b) * 1.3, 1)) for j, b in enumerate(ns)] for i, a in enumerate(ns)]
    mins = [[0 if i == j else max(1, round(km[i][j] * 2.5)) for j in range(len(ns))] for i in range(len(ns))]
    doc = {"city_id": c, "profile": "driving-car", "computed_on": "2026-10-01",
           "nodes": [n[0] for n in ns], "km": km, "minutes_free_flow": mins}
    (out / "matrices" / f"{c}.json").write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
print("ok")
