"""Build data/curated/local_transport.csv (T09).

    python -m datatools.curation.local_transport

Tariffs are (min_fare, min_km, per_km beyond min_km), read from opened pages.
Missing tariffs follow 001 Spec 5.8: the state's tariff (statewide: approx false;
another city's in the same state: approx true), else the median over cities with
their own tariff (approx true).
"""

from statistics import median

from datatools.curation.common import CURATED, fetched_on, latest, round_half_up, write_csv

CITIES = ["JAI", "AGR", "HMP", "MUN", "RSH", "DJL", "GOA", "PDY", "DEL", "BOM", "BLR", "CCU", "HYD", "VNS", "MAA"]
STATE = {"JAI": "RJ", "AGR": "UP", "VNS": "UP", "HMP": "KA", "BLR": "KA", "MUN": "KL", "RSH": "UK", "DJL": "WB",
         "CCU": "WB", "GOA": "GA", "PDY": "PY", "DEL": "DL", "BOM": "MH", "HYD": "TG", "MAA": "TN"}
CAP = {"auto": 3, "cab": 4}

U_BLR = "https://thesouthfirst.com/karnataka/auto-fares-revised-in-bengaluru-effective-from-august-1/"
U_KA = "https://www.theweek.in/news/biz-tech/2024/02/04/karnataka-govt-fixes-uniform-charges-for-ola-uber-city-taxis-here-are-the-new-fares.amp.html"
U_DEL = "https://www.businesstoday.in/latest/story/auto-and-taxi-fares-hiked-in-delhi-check-new-rates-359828-2023-01-11"
U_DEL2 = "https://www.dnaindia.com/delhi/report-delhi-government-revises-autorickshaw-taxi-fares-list-of-new-rates-2996721"
U_BOM = "https://www.outlookbusiness.com/news/taxi-auto-rickshaw-fares-hiked-in-mumbai-region"
U_HYD = "https://www.deccanchronicle.com/southern-states/telangana/state-revises-autorickshaw-fares-1992627"
U_KL = "https://onmanorama.com/news/kerala/2022/05/01/hike-in-bus-auto-taxi-fares-kerala.html"
U_WB = "https://wbxpress.com/taxi-fares-2018/"
U_TN = "https://www.stationeryprinting.tn.gov.in/extraordinary/2013/240-Ex-II-2.pdf"

# Own tariffs: (city, mode) -> (min_fare, min_km, per_km, note, urls)
OWN = {
    ("BLR", "auto"): (36, 2.0, 18.0, "Bengaluru RTA: Rs 36 first 2 km, Rs 18/km", [U_BLR]),
    ("DEL", "auto"): (30, 1.5, 11.0, "Delhi: Rs 30 first 1.5 km, Rs 11/km", [U_DEL]),
    ("BOM", "auto"): (27, 1.5, 18.22, "MMRTA: Rs 27 first 1.5 km, Rs 18.22/km", [U_BOM]),
    ("HYD", "auto"): (30, 1.6, 14.0, "Telangana GO: Rs 30 first 1.6 km, Rs 14/km", [U_HYD]),
    ("MAA", "auto"): (25, 1.8, 12.0, "G.O. Ms. No. 611 (2013), Chennai Metropolitan area: Rs 25 first 1.8 km, Rs 12/km", [U_TN]),
    ("BLR", "cab"): (100, 4.0, 24.0, "Karnataka order, cabs up to Rs 10 lakh: Rs 100 up to 4 km, Rs 24/km", [U_KA]),
    ("DEL", "cab"): (40, 1.0, 20.0, "Delhi AC taxi: Rs 40 meter-down for the initial 1 km, Rs 20/km", [U_DEL, U_DEL2]),
    ("BOM", "cab"): (33, 1.5, 21.90, "MMRTA black-and-yellow taxi: Rs 33 first 1.5 km, Rs 21.90/km", [U_BOM]),
    ("CCU", "cab"): (30, 2.0, 15.0, "West Bengal meter taxi (Kolkata and all regions): Rs 30 up to 2 km, Rs 3 per 200 m", [U_WB]),
}
# Statewide notifications usable for other cities in the state: (state, mode) -> own key
STATEWIDE = {("KL", "auto"): (30, 1.5, 15.0, "Kerala statewide: Rs 30 for 1.5 km, Rs 15/km", [U_KL]),
             ("KA", "cab"): OWN[("BLR", "cab")], ("WB", "cab"): OWN[("CCU", "cab")]}


def main() -> None:
    d = fetched_on()
    rows = []
    for mode in ("auto", "cab"):
        own = [v for (c, m), v in OWN.items() if m == mode]
        med = (round_half_up(median(v[0] for v in own)), median(v[1] for v in own), median(v[2] for v in own))
        med_cities = ",".join(sorted(c for (c, m) in OWN if m == mode))
        med_urls = sorted({u for v in own for u in v[4]})
        for city in CITIES:
            st = STATE[city]
            if (city, mode) in OWN:
                mf, mk, pk, note, urls = OWN[(city, mode)]
                approx, how = False, f"own tariff: {note}"
            elif (st, mode) in STATEWIDE:
                mf, mk, pk, note, urls = STATEWIDE[(st, mode)]
                approx, how = False, f"statewide tariff of the state: {note}"
            elif any(STATE[c] == st for (c, m) in OWN if m == mode):
                src_city = next(c for (c, m) in OWN if m == mode and STATE[c] == st)
                mf, mk, pk, note, urls = OWN[(src_city, mode)]
                approx, how = True, f"APPROX: no own tariff; uses {src_city} tariff from the same state: {note}"
            else:
                mf, mk, pk = med
                urls = med_urls
                approx, how = True, f"APPROX: no tariff for the city or state; median of {med_cities} {mode} tariffs"
            src = f"{how} | " + " ; ".join(urls)
            rows.append([city, mode, mf, f"{mk:g}", f"{pk:.2f}", CAP[mode], "true" if approx else "false", src,
                         latest(*(d[u] for u in urls))])
        print(f"{mode} median over {med_cities}: {med}")
    rows.sort(key=lambda r: (CITIES.index(r[0]), r[1]))
    write_csv(CURATED / "local_transport.csv",
              ["city_id", "mode", "min_fare", "min_km", "per_km", "capacity", "approx", "source", "checked_on"], rows)


if __name__ == "__main__":
    main()
