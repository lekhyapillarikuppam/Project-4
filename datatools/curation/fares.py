"""Build data/raw/fare_samples.csv and data/curated/fare_rates.csv (T08).

    python -m datatools.curation.fares

Every sample is a real fare read from an opened page (data/raw/evidence/pages.csv).
fare = base_fare + per_km x km is fitted by least squares per class; min_fare is the
lowest sample fare.
"""

from datatools.curation.common import CURATED, RAW, fetched_on, haversine_km, latest, write_csv

E = "https://erail.in/train-fare/"
C = "https://www.confirmtkt.com/train-schedule/"
IX = "https://www.ixigo.com/buses/"
IF = "https://www.ixigo.com/cheap-flights/"
W = "https://en.wikipedia.org/wiki/"

AIRPORTS = {  # Wikipedia infobox coordinates
    "DEL": (28.56861, 77.11222, "Indira_Gandhi_International_Airport"),
    "JAI": (26.82417, 75.81222, "Jaipur_International_Airport"),
    "BLR": (13.19889, 77.70556, "Kempegowda_International_Airport"),
    "CCU": (22.65472, 88.44667, "Netaji_Subhas_Chandra_Bose_International_Airport"),
    "MAA": (12.98222, 80.16361, "Chennai_International_Airport"),
    "HYD": (17.23000, 78.43194, "Rajiv_Gandhi_International_Airport"),
    "BOM": (19.08861, 72.86806, "Chhatrapati_Shivaji_Maharaj_International_Airport"),
    "GOI": (15.38083, 73.83139, "Dabolim_Airport"),
}

# train, confirmtkt slug, route, km, SL, 3A, 2A
TRAINS = [
    ("12657", "12657-Chennai-Bangalore-Mail", "MAS-SBC", 362.0, 275, 695, 965),
    ("16021", "16021-Kaveri-Express", "MAS-AP", 505.0, 325, 855, 1210),
    ("12633", "12633-Kanyakumari-Express", "MS-CAPE", 742.0, 451, 1165, 1625),
    ("12559", "12559-Shiv-Ganga-Express", "BNRS-NDLS", 757.0, 454, 1170, 1645),
    ("12916", "12916-Ashram-Express", "DLI-SBIB", 928.0, 516, 1330, 1865),
    ("12955", "12955-Jaipur-Superfast-Express", "MMCT-JP", 1159.0, 597, 1520, 2150),
    ("12841", "12841-Coromandel-Express", "HWH-MAS", 1662.0, 746, 1900, 2695),
    ("12723", "12723-Telangana-Express", "HYB-NDLS", 1683.0, 753, 1915, 2720),
    ("12627", "12627-Karnataka-Express", "SBC-NDLS", 2395.0, 930, 2330, 3335),
    ("12625", "12625-Kerala-Express", "TVC-NDLS", 3040.0, 1066, 2640, 3805),
]
# ixigo route slug, stated km, lowest 'From' fare among pure AC sleepers
BUSES = [
    ("delhi-dehradun-sts", 198.0, 599), ("delhi-jaipur-sts", 241.0, 759), ("bangalore-chennai-sts", 293.0, 719),
    ("mumbai-goa-sts", 402.0, 1100), ("bangalore-hyderabad-sts", 500.0, 1149),
]
# ixigo slug, from airport, to airport, headline 'Fares starting @' fare
FLIGHTS = [
    ("delhi-jaipur-del-jai", "DEL", "JAI", 2519), ("bangalore-chennai-blr-maa", "BLR", "MAA", 4105),
    ("mumbai-goa-bom-goi", "BOM", "GOI", 3573), ("bangalore-hyderabad-blr-hyd", "BLR", "HYD", 4284),
    ("delhi-mumbai-del-bom", "DEL", "BOM", 5773), ("hyderabad-delhi-hyd-del", "HYD", "DEL", 8228),
    ("delhi-kolkata-del-ccu", "DEL", "CCU", 8293), ("chennai-kolkata-maa-ccu", "MAA", "CCU", 7753),
    ("bangalore-delhi-blr-del", "BLR", "DEL", 9248),
]
COMFORT = {"SL": 0.2, "3A": 0.6, "2A": 0.8, "ACS": 0.5, "Y": 0.9}
TRAIN_FIT_MAX_KM = 2000


def air_km(a: str, b: str) -> float:
    return round(haversine_km(AIRPORTS[a][0], AIRPORTS[a][1], AIRPORTS[b][0], AIRPORTS[b][1]), 1)


def samples() -> list[list]:
    d = fetched_on()
    out = []
    for t, slug, route, km, *fares in TRAINS:
        when = latest(d[E + t], d[C + slug])
        for cls, fare in zip(("SL", "3A", "2A"), fares):
            out.append(["train", cls, f"{t} {route} (full route)", km, C + slug, fare, E + t,
                        "general quota fare, 1 adult, full route", when])
    for slug, km, fare in BUSES:
        out.append(["bus", "ACS", slug.removesuffix("-sts"), km, IX + slug + " (stated distance)", fare, IX + slug,
                    "lowest listed 'From' fare among pure AC sleepers", d[IX + slug]])
    for slug, a, b, fare in FLIGHTS:
        src = f"great-circle between {W}{AIRPORTS[a][2]} and {W}{AIRPORTS[b][2]} coordinates"
        out.append(["flight", "Y", f"{a}-{b}", air_km(a, b), src, fare, IF + slug,
                    "headline 'Fares starting @' fare", latest(d[IF + slug], d[W + AIRPORTS[a][2]], d[W + AIRPORTS[b][2]])])
    return out


def fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


def main() -> None:
    S = samples()
    write_csv(RAW / "fare_samples.csv",
              ["mode", "class", "route", "distance_km", "distance_source", "fare_inr", "fare_source", "fare_basis", "observed_on"], S)
    rows = []
    for mode, cls in (("train", "SL"), ("train", "3A"), ("train", "2A"), ("bus", "ACS"), ("flight", "Y")):
        pts = [(r[3], r[5], r[8], r[2]) for r in S if r[0] == mode and r[1] == cls]
        scope = ""
        if mode == "train":
            # Rail fares taper with distance; fit the range the trips actually use.
            pts = [p for p in pts if p[0] <= TRAIN_FIT_MAX_KM]
            scope = f" with distance <= {TRAIN_FIT_MAX_KM} km"
        a, b = fit([p[0] for p in pts], [p[1] for p in pts])
        base, per_km = round(a), round(b, 2)
        pct = [(base + per_km * x - y) / y * 100 for x, y, _, _ in pts]
        worst = max(pct, key=abs)
        src = (f"least-squares fit fare = base_fare + per_km x km over the {len(pts)} samples{scope} in data/raw/fare_samples.csv "
               f"(largest residual {worst:+.1f}%); min_fare = lowest fitted sample fare; comfort_value = 001 Spec 5.4 default")
        rows.append([mode, cls, base, f"{per_km:.2f}", min(p[1] for p in pts), COMFORT[cls], src, latest(*(p[2] for p in pts))])
        print(f"{mode} {cls}: n={len(pts)} base={base} per_km={per_km:.2f} min={min(p[1] for p in pts)}")
        for (x, y, _, route), e in zip(pts, pct):
            print(f"    {route:32s} {x:7.1f} km  Rs {y:5d}  fit Rs {base + per_km * x:7.0f}  {e:+6.1f}%")
    write_csv(CURATED / "fare_rates.csv",
              ["mode", "class", "base_fare", "per_km", "min_fare", "comfort_value", "source", "checked_on"], rows)


if __name__ == "__main__":
    main()
