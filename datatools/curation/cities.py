"""Build data/curated/cities.csv and food.csv (T06).

    python -m datatools.curation.cities

Centres are hand-chosen (001 Spec §3); the reason is written into `source`.
food_multiplier = city Numbeo "Meal for Two, Mid-Range" / India figure; 1.0 as a
marked approximation where Numbeo has no page.
"""

from datatools.curation.common import CURATED, fetched_on, latest, write_csv

W = "https://en.wikipedia.org/wiki/"
NB = "https://www.numbeo.com/cost-of-living/in/"
NB_INDIA = "https://www.numbeo.com/cost-of-living/country_result.jsp?country=India"
INDIA_MID = 1000          # Numbeo India, Meal for Two at a Mid-Range Restaurant
INDIA_CHEAP = 200         # Numbeo India, Meal at an Inexpensive Restaurant
SPEC_TF = "traffic_factor: 001 Spec 5.1 suggested value"
KEPT = "Wikipedia infobox reference point for the city, reviewed and kept as the core"

# city, name, lat, lon, coord page, centre reason, traffic factor, Numbeo page, mid-range meal for two
CITIES = [
    ("JAI", "Jaipur", "26.915", "75.820", "Jaipur", KEPT, 1.2, "Jaipur", 1200),
    ("AGR", "Agra", "27.18", "78.02", "Agra", KEPT, 1.2, "Agra", 1500),
    ("HMP", "Hampi", "15.33444", "76.46222", "Hampi", KEPT, 1.1, None, None),
    ("MUN", "Munnar", "10.08917", "77.05972", "Munnar", KEPT, 1.1, None, None),
    ("RSH", "Rishikesh", "30.10833", "78.29722", "Rishikesh", KEPT, 1.1, "Rishikesh-India", 850),
    ("DJL", "Darjeeling", "27.03750", "88.26306", "Darjeeling", KEPT, 1.1, "Darjeeling-India", 1150),
    ("GOA", "Goa", "15.49889", "73.82778", "Panaji",
     "Panaji, the state capital (https://en.wikipedia.org/wiki/Goa: 'Panaji (Panjim) is the state's capital'); the Goa page gives a state centroid", 1.2, "Goa", 1500),
    ("PDY", "Pondicherry", "11.93401", "79.82903", "Pondicherry", KEPT, 1.2, "Pondicherry", 850),
    ("DEL", "Delhi", "28.6139", "77.2089", "New_Delhi", KEPT, 1.4, "Delhi", 2000),
    ("BOM", "Mumbai", "18.935", "72.8359", "Fort_(Mumbai_precinct)",
     "Fort precinct, 'the heart of the financial markets of the city' with CSMT at its northern edge; the Mumbai infobox point lies in the suburbs", 1.4, "Mumbai", 2000),
    ("BLR", "Bengaluru", "12.97889", "77.59167", "Bangalore", KEPT, 1.4, "Bangalore", 1700),
    ("CCU", "Kolkata", "22.5675", "88.37", "Kolkata", KEPT, 1.4, "Kolkata", 1300),
    ("HYD", "Hyderabad", "17.36167", "78.47472", "Hyderabad", KEPT, 1.4, "Hyderabad", 1500),
    ("VNS", "Varanasi", "25.31889", "83.01278", "Varanasi", KEPT, 1.2, "Varanasi", 750),
    ("MAA", "Chennai", "13.0732", "80.2609", "Egmore",
     "Egmore: Government Museum, one of the two main rail termini, a shopping district; the Chennai infobox point coincides with Chennai Central station", 1.4, "Chennai", 1200),
]


def main() -> None:
    dates = fetched_on()
    rows = []
    for cid, name, lat, lon, page, reason, tf, nb, mid in CITIES:
        coord_url = W + page
        used = [dates[coord_url]]
        src = [f"centre: {reason}; coords {coord_url}", SPEC_TF]
        if mid is None:
            fm = "1.00"
            src.append("food_multiplier: APPROXIMATION 1.0, no cost-of-living source for this city (001 Spec 5.1)")
        else:
            fm = f"{mid / INDIA_MID:.2f}"
            used += [dates[NB + nb], dates[NB_INDIA]]
            src.append(f"food_multiplier: {NB}{nb} Meal for Two Mid-Range Rs {mid} / India Rs {INDIA_MID} ({NB_INDIA})")
        rows.append([cid, name, lat, lon, f"{tf:.1f}", fm, " | ".join(src), latest(*used)])
    write_csv(CURATED / "cities.csv",
              ["city_id", "name", "lat", "lon", "traffic_factor", "food_multiplier", "source", "checked_on"], rows)

    d = dates[NB_INDIA]
    mid_food = 3 * INDIA_MID // 2
    write_csv(CURATED / "food.csv", ["comfort", "base_per_person_per_day", "source", "checked_on"], [
        ["budget", 3 * INDIA_CHEAP, f"{NB_INDIA}: 3 x Meal at an Inexpensive Restaurant Rs {INDIA_CHEAP}", d],
        ["mid", mid_food, f"{NB_INDIA}: 3 x (Meal for Two at a Mid-Range Restaurant Rs {INDIA_MID} / 2)", d],
        ["premium", 2 * mid_food, "assumption A-08: 2 x the mid allowance (Part B 8, 001 Spec 5.7)", d],
    ])


if __name__ == "__main__":
    main()
