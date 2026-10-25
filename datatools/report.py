"""Dataset report (001 Spec DATA-FR-12, DATA-AT-03, DATA-AT-05, DATA-AT-06; T23).

    python -m datatools.report                        per-city counts, tag coverage, approximation shares
    python -m datatools.report --db [--schema ref]    compare database row counts with the files (DATA-AT-03)
    python -m datatools.report --sample 20 10 --seed 7 [--out data/spot_check.md]
                                                      spot-check sample: attractions, hotels, every fare row
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from datatools import rules
from datatools.curation.common import read_csv
from datatools.validate import DEFAULT_DATA

ROOT = Path(__file__).resolve().parents[1]
APPROX_DIR = ROOT / "data" / "raw" / "matrices"


def share(n: int, total: int) -> str:
    return f"{n}/{total} ({100 * n / total:.0f}%)" if total else "0/0"


def attractions(data: Path) -> dict[str, list[dict]]:
    return {c: read_csv(data / rules.ATTRACTIONS_DIR / f"{c}.csv") for c in rules.CITY_CODES}


def counts(data: Path) -> None:
    hotels = read_csv(data / rules.HOTELS_FILE)
    hubs = read_csv(data / rules.HUBS_FILE)
    attr = attractions(data)
    print("city  attractions  hotels(b/m/p)  hubs  free  food  required tags")
    for c in rules.CITY_CODES:
        rows = attr[c]
        tiers = Counter(h["tier"] for h in hotels if h["city_id"] == c)
        tags = Counter(t for r in rows for t in r["tags"].split(";"))
        req = ", ".join(f"{t} {tags[t]}" for t in rules.REQUIRED_TAGS[c])
        print(f"{c}   {len(rows):>11}  {tiers['budget']}/{tiers['mid']}/{tiers['premium']:<9}  "
              f"{sum(h['city_id'] == c for h in hubs):>4}  {sum(r['entry_fee'] == '0' for r in rows):>4}  "
              f"{tags['food']:>4}  {req}")
    all_attr = [r for rows in attr.values() for r in rows]
    pairs = read_csv(data / rules.PAIRS_FILE)
    durations = [(p, m) for p in pairs for m in rules.TRANSPORT_MODES if p[f"{m}_available"] == "true"]
    local = read_csv(data / rules.LOCAL_FILE)
    print("\nApproximations (DATA-FR-12)")
    print("  pairs with rail_km copied from road_km:", share(sum(p["rail_km_approx"] == "true" for p in pairs), len(pairs)))
    print("  pairs with any formula duration:      ",
          share(sum(any(p[f"{m}_minutes_approx"] == "true" for m in rules.TRANSPORT_MODES if p[f"{m}_available"] == "true")
                    for p in pairs), len(pairs)))
    print("  available durations from the formula:  ", share(sum(p[f"{m}_minutes_approx"] == "true" for p, m in durations), len(durations)))
    for col in ("visit_approx", "hours_approx", "fee_approx"):
        print(f"  attractions {col + ':':<14}            ", share(sum(r[col] == "true" for r in all_attr), len(all_attr)))
    print("  local transport tariffs approx:        ", share(sum(r["approx"] == "true" for r in local), len(local)))
    unroutable = below = cells = 0
    for c in rules.CITY_CODES:
        f = APPROX_DIR / f"{c}_approx.json"
        m = data / rules.MATRICES_DIR / f"{c}.json"
        if f.exists() and m.exists():
            a = json.loads(f.read_text(encoding="utf-8"))
            n = len(json.loads(m.read_text(encoding="utf-8"))["nodes"])
            unroutable, below, cells = unroutable + len(a["unroutable"]), below + len(a["below_rounding"]), cells + n * (n - 1)
    print("  matrix cells unroutable (fallback):    ", share(unroutable, cells))
    print("  matrix cells raised to the minimum:    ", share(below, cells))


def expected_counts(data: Path) -> dict[str, int]:
    n = {"cities": rules.CITIES_FILE, "hubs": rules.HUBS_FILE, "fare_rates": rules.FARES_FILE, "food": rules.FOOD_FILE,
         "local_transport": rules.LOCAL_FILE, "hotels": rules.HOTELS_FILE}
    out = {t: len(read_csv(data / f)) for t, f in n.items()}
    out["city_pairs"] = 2 * len(read_csv(data / rules.PAIRS_FILE))   # loaded in both directions
    out["attractions"] = sum(len(r) for r in attractions(data).values())
    out["travel_matrix"] = sum(len(json.loads((data / rules.MATRICES_DIR / f"{c}.json").read_text(encoding="utf-8"))["nodes"]) ** 2
                               for c in rules.CITY_CODES)
    out["data_version"] = 1
    return out


def db_check(data: Path, schema: str) -> int:
    from datatools.load import connect, read_version
    exp = expected_counts(data)
    bad = 0
    with connect() as conn, conn.cursor() as cur:
        for t, n in exp.items():
            cur.execute(f"SELECT count(*) FROM {schema}.{t}")
            got = cur.fetchone()[0]
            bad += got != n
            print(f"{schema}.{t}: database {got}, files {n}" + ("" if got == n else "  MISMATCH"))
        cur.execute(f"SELECT version, compiled, loaded_at FROM {schema}.data_version")
        v, compiled, at = cur.fetchone()
    ver = read_version(data)
    ok = (v, compiled) == (ver["version"], ver["compiled"])
    print(f"version: database {v} / {compiled} (loaded {at:%Y-%m-%d %H:%M}), VERSION {ver['version']} / {ver['compiled']}"
          + ("" if ok else "  MISMATCH"))
    return 0 if bad == 0 and ok else 1


def sample(data: Path, n_attr: int, n_hotels: int, seed: int, out: Path | None) -> None:
    rng = random.Random(seed)
    attr = sorted((r for rows in attractions(data).values() for r in rows), key=lambda r: r["attraction_id"])
    hotels = sorted(read_csv(data / rules.HOTELS_FILE), key=lambda r: r["hotel_id"])
    fares = read_csv(data / rules.FARES_FILE)
    def esc(s: str) -> str:
        return s.replace("|", "\\|")
    lines = ["# Spot check (DATA-AT-05)", "",
             f"Sample: `python -m datatools.report --sample {n_attr} {n_hotels} --seed {seed}`. Re-check each row against its "
             "source and fill **Result** with `match` or `mismatch: <what differs>`. Pass when at least 18 of 20 attractions, "
             "10 of 10 hotels and every fare row match.", "",
             "## Attractions", "", "| ID | Name | Hours | Closed | Fee | Visit | Source | Result |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rng.sample(attr, n_attr), key=lambda r: r["attraction_id"]):
        lines.append(f"| {r['attraction_id']} | {esc(r['name'])} | {r['open_time']}–{r['close_time']} | {r['closed_weekdays'] or '—'} | "
                     f"{r['entry_fee']} | {r['visit_minutes']} | {esc(r['source'])} |  |")
    lines += ["", "## Hotels", "", "| ID | Name | Tier | Price per room night | Source | Result |", "|---|---|---|---|---|---|"]
    for r in sorted(rng.sample(hotels, n_hotels), key=lambda r: r["hotel_id"]):
        lines.append(f"| {r['hotel_id']} | {esc(r['name'])} | {r['tier']} | {r['price_per_room_night']} | {esc(r['source'])} |  |")
    lines += ["", "## Fare rates (all rows)", "", "| Mode | Class | Base fare | Per km | Min fare | Source | Result |",
              "|---|---|---|---|---|---|---|"]
    for r in fares:
        lines.append(f"| {r['mode']} | {r['class']} | {r['base_fare']} | {r['per_km']} | {r['min_fare']} | {esc(r['source'])} |  |")
    lines += ["", "## Summary", "", "Attractions matching: __ / 20 · Hotels matching: __ / 10 · Fare rows matching: __ / 5 · "
              "Checked by: ______ on ______", ""]
    text = "\n".join(lines)
    if out:
        out.write_text(text, encoding="utf-8")
        print("wrote", out)
    else:
        print(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datatools.report", description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--db", action="store_true", help="compare database row counts with the files")
    ap.add_argument("--schema", default="ref")
    ap.add_argument("--sample", nargs=2, type=int, metavar=("ATTRACTIONS", "HOTELS"))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.db:
        return db_check(args.data, args.schema)
    if args.sample:
        sample(args.data, *args.sample, args.seed, args.out)
        return 0
    counts(args.data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
