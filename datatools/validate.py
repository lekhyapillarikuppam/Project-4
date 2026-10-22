"""Dataset validator (001 Spec §3–5, §7; 001 Plan §4).

    python -m datatools.validate [--data DIR] [--cities JAI,AGR]

Pass 1 checks each row (models.py). Pass 2 checks across rows and files.
Prints `file:row:field: message` for each finding, then `N errors, M warnings`.
Exits 1 if there is any error (DATA-FR-10).

`--cities` replaces the 15 expected cities with a subset. It exists for the test
fixtures only, so the "exactly 15 cities / 105 pairs" rules can be relaxed.

To avoid knock-on noise, count and coverage checks for a city are skipped when one
of that city's rows in the same file could not be parsed; fixing the parse error
brings them back.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

from pydantic import ValidationError

from datatools import rules
from datatools.geo import haversine_km
from datatools.io import Issue, Table, read_csv, read_json, read_version
from datatools.models import (
    Attraction, City, CityPair, FareRate, Food, Hotel, Hub, LocalTransport, Matrix,
)

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "data" / "curated"



class Validator:
    def __init__(self, data_dir: Path, cities: list[str] | None = None):
        self.data = Path(data_dir)
        self.expected = list(cities) if cities else list(rules.CITY_CODES)
        self.issues: list[Issue] = []
        self.centres: dict[str, tuple[float, float]] = {}

    # --- helpers ----------------------------------------------------------

    def error(self, file: str, row, field: str, code: str, message: str) -> None:
        self.issues.append(Issue(file, str(row), field, code, message))

    def warn(self, file: str, row, field: str, code: str, message: str) -> None:
        self.issues.append(Issue(file, str(row), field, code, message, "warning"))

    def load(self, rel: str, model, context: dict | None = None) -> Table:
        """Pass 1 for one CSV: parse every row, then run its row checks."""
        table = read_csv(self.data, rel, model, context)
        self.issues += table.issues
        for row in table.rows:
            if row.model is not None:
                for p in row.model.row_checks():
                    self.error(rel, row.line, p.field, p.code, p.message)
        return table

    def in_scope(self, file: str, line, field: str, city: str) -> bool:
        """A known city code that is not one of the expected cities is an error."""
        if city not in rules.CITY_CODES:
            return False   # already reported by the row check
        if city not in self.expected:
            self.error(file, line, field, "unknown_city", f"city {city} is not in the dataset")
            return False
        return True

    def check_distance(self, file: str, line, city: str, lat: float, lon: float, limit: float) -> None:
        if city not in self.centres:
            return
        km = haversine_km(lat, lon, *self.centres[city])
        if km > limit:
            self.error(file, line, "lat", "too_far",
                       f"{km:.1f} km from the {city} centre; limit is {limit} km")

    @staticmethod
    def broken_cities(table: Table, key: str = "city_id") -> set[str]:
        return {r.raw.get(key) for r in table.failed}

    # --- checks -----------------------------------------------------------

    def run(self) -> list[Issue]:
        self.check_version()
        self.check_cities()
        hubs = self.check_hubs()
        self.check_pairs(hubs)
        self.check_fares()
        attraction_ids = self.check_attractions()
        hotel_ids = self.check_hotels()
        self.check_food()
        self.check_local()
        self.check_matrices(hubs, attraction_ids, hotel_ids)
        return sorted(self.issues, key=_sort_key)

    def check_version(self) -> None:
        rel = rules.VERSION_FILE
        values, issues = read_version(self.data, rel)
        self.issues += issues
        if values is None:
            return
        for key, pattern, example in (("version", rules.VERSION_PATTERN, "1.0"),
                                      ("compiled", rules.COMPILED_PATTERN, "2026-11")):
            if key not in values:
                self.error(rel, "-", key, "bad_version", f"missing line {key}=…")
            elif not re.match(pattern, values[key]):
                self.error(rel, "-", key, "bad_version", f"{key} must look like {example}, got {values[key]!r}")

    def check_cities(self) -> None:
        table = self.load(rules.CITIES_FILE, City)
        seen = Counter()
        for row in table.rows:
            if row.model is None:
                continue
            c = row.model
            seen[c.city_id] += 1
            if seen[c.city_id] > 1:
                self.error(table.file, row.line, "city_id", "duplicate_id", f"{c.city_id} listed twice")
            elif c.city_id in rules.CITY_CODES and c.city_id not in self.expected:
                self.error(table.file, row.line, "city_id", "unknown_city", f"city {c.city_id} is not in the dataset")
            else:
                self.centres[c.city_id] = (c.lat, c.lon)
        if table.readable and not table.failed:
            for city in self.expected:
                if city not in seen:
                    self.error(table.file, "-", "city_id", "missing_city", f"city {city} is missing")

    def check_hubs(self) -> dict[str, set[str]] | None:
        """Returns the hub modes per city, or None if hubs.csv could not be read."""
        table = self.load(rules.HUBS_FILE, Hub)
        hubs: dict[str, set[str]] = defaultdict(set)
        for row in table.rows:
            h = row.model
            if h is None or not self.in_scope(table.file, row.line, "city_id", h.city_id):
                continue
            if h.mode in hubs[h.city_id]:
                self.error(table.file, row.line, "mode", "duplicate_id", f"second {h.mode} hub for {h.city_id}")
            hubs[h.city_id].add(h.mode)
        broken = self.broken_cities(table)
        if table.readable:
            for city in self.expected:
                if not hubs.get(city) and city not in broken:
                    self.error(table.file, "-", "city_id", "city_no_hub", f"{city} has no hub")
        return hubs if table.readable else None

    def check_pairs(self, hubs: dict[str, set[str]] | None) -> None:
        table = self.load(rules.PAIRS_FILE, CityPair)
        seen: set[tuple[str, str]] = set()
        for row in table.rows:
            p = row.model
            if p is None:
                continue
            if not (self.in_scope(table.file, row.line, "city_a", p.city_a)
                    and self.in_scope(table.file, row.line, "city_b", p.city_b)):
                continue
            key = (p.city_a, p.city_b)
            if key in seen:
                self.error(table.file, row.line, "city_a", "duplicate_id", f"pair {p.city_a}-{p.city_b} listed twice")
            seen.add(key)
            for mode in p.available_modes() if hubs is not None else ():
                for city in key:
                    if mode not in hubs.get(city, set()):
                        self.error(table.file, row.line, f"{mode}_available", "pair_mode_without_hub",
                                   f"{mode} is available but {city} has no {mode} hub")
        if table.readable and not table.failed:
            for a, b in combinations(sorted(self.expected), 2):
                if (a, b) not in seen:
                    self.error(table.file, "-", "-", "missing_pair", f"pair {a}-{b} is missing")

    def check_fares(self) -> None:
        table = self.load(rules.FARES_FILE, FareRate)
        seen = set()
        for row in table.rows:
            f = row.model
            if f is None:
                continue
            key = (f.mode, f.fare_class)
            if key in seen:
                self.error(table.file, row.line, "class", "duplicate_id", f"{f.mode} {f.fare_class} listed twice")
            seen.add(key)
        if table.readable and not table.failed:
            for mode, cls in rules.FARE_CLASSES:
                if (mode, cls) not in seen:
                    self.error(table.file, "-", "class", "missing_fare", f"{mode} {cls} is missing")

    def check_attractions(self) -> dict[str, list[str] | None]:
        """Returns the attraction IDs per city as written in each file (for the matrix
        check), or None for a city whose file could not be read."""
        ids_by_city: dict[str, list[str]] = {}
        all_ids: set[str] = set()
        adir = self.data / rules.ATTRACTIONS_DIR
        if adir.is_dir():
            for path in sorted(adir.glob("*.csv")):
                if path.stem not in self.expected:
                    self.error(f"{rules.ATTRACTIONS_DIR}/{path.name}", "-", "-", "unexpected_file",
                               f"no city {path.stem} in the dataset")
        for city in self.expected:
            rel = f"{rules.ATTRACTIONS_DIR}/{city}.csv"
            table = self.load(rel, Attraction)
            ids_by_city[city] = ([r.raw["attraction_id"] for r in table.rows if r.raw.get("attraction_id")]
                                 if table.readable else None)
            usable = []
            for row in table.rows:
                a = row.model
                if a is None:
                    continue
                if a.attraction_id in all_ids:
                    self.error(rel, row.line, "attraction_id", "duplicate_id", f"{a.attraction_id} listed twice")
                all_ids.add(a.attraction_id)
                if a.city_id not in rules.CITY_CODES:
                    continue
                if a.city_id != city:
                    self.error(rel, row.line, "city_id", "wrong_file", f"{a.city_id} attraction in {city} file")
                    continue
                self.check_distance(rel, row.line, city, a.lat, a.lon, rules.ATTRACTION_MAX_KM_FROM_CENTRE)
                usable.append(a)
            if not table.readable or table.failed:
                continue
            lo, hi = rules.ATTRACTIONS_PER_CITY
            if not lo <= len(table.rows) <= hi:
                self.error(rel, "-", "-", "bad_attraction_count", f"{city} has {len(table.rows)} attractions; needs {lo}–{hi}")
            free = sum(1 for a in usable if a.entry_fee == 0)
            if free < rules.MIN_FREE_ATTRACTIONS:
                self.error(rel, "-", "entry_fee", "too_few_free",
                           f"{city} has {free} free attractions; needs {rules.MIN_FREE_ATTRACTIONS}")
            for tag in rules.REQUIRED_TAGS.get(city, ()):
                n = sum(1 for a in usable if tag in a.tags)
                if n < rules.MIN_ATTRACTIONS_PER_REQUIRED_TAG:
                    self.error(rel, "-", "tags", "tag_coverage",
                               f"{city} has {n} '{tag}' attractions; needs {rules.MIN_ATTRACTIONS_PER_REQUIRED_TAG}")
        return ids_by_city

    def check_hotels(self) -> dict[str, list[str]] | None:
        """Returns the hotel IDs per city, or None if hotels.csv could not be read."""
        table = self.load(rules.HOTELS_FILE, Hotel)
        ids_by_city: dict[str, list[str]] = defaultdict(list)
        for row in table.rows:
            if row.raw.get("hotel_id") and row.raw.get("city_id"):
                ids_by_city[row.raw["city_id"]].append(row.raw["hotel_id"])
        seen: set[str] = set()
        by_city: dict[str, list[Hotel]] = defaultdict(list)
        for row in table.rows:
            h = row.model
            if h is None:
                continue
            if h.hotel_id in seen:
                self.error(table.file, row.line, "hotel_id", "duplicate_id", f"{h.hotel_id} listed twice")
            seen.add(h.hotel_id)
            if not self.in_scope(table.file, row.line, "city_id", h.city_id):
                continue
            self.check_distance(table.file, row.line, h.city_id, h.lat, h.lon, rules.HOTEL_MAX_KM_FROM_CENTRE)
            by_city[h.city_id].append(h)
        if not table.readable:
            return None
        broken = self.broken_cities(table)
        lo, hi = rules.HOTELS_PER_TIER
        for city in self.expected:
            if city in broken:
                continue
            hotels = by_city.get(city, [])
            for tier in rules.HOTEL_TIERS:
                n = sum(1 for h in hotels if h.tier == tier)
                if not lo <= n <= hi:
                    self.error(table.file, "-", "tier", "bad_hotel_count", f"{city} has {n} {tier} hotels; needs {lo}–{hi}")
            if len(hotels) > 1 and all(
                haversine_km(a.lat, a.lon, b.lat, b.lon) <= rules.HOTEL_SPREAD_WARN_KM
                for a, b in combinations(hotels, 2)
            ):
                self.warn(table.file, "-", "lat", "hotels_clustered",
                          f"all {city} hotels are within {rules.HOTEL_SPREAD_WARN_KM} km of each other")
        return ids_by_city

    def check_food(self) -> None:
        table = self.load(rules.FOOD_FILE, Food)
        seen = Counter(f.comfort for f in table.models)
        for row in table.rows:
            if row.model is not None and seen[row.model.comfort] > 1:
                self.error(table.file, row.line, "comfort", "duplicate_id", f"{row.model.comfort} listed twice")
        if table.readable and not table.failed:
            for comfort in rules.FOOD_ROWS:
                if comfort not in seen:
                    self.error(table.file, "-", "comfort", "missing_row", f"{comfort} row is missing")

    def check_local(self) -> None:
        table = self.load(rules.LOCAL_FILE, LocalTransport)
        seen: dict[str, set[str]] = defaultdict(set)
        for row in table.rows:
            t = row.model
            if t is None or not self.in_scope(table.file, row.line, "city_id", t.city_id):
                continue
            if t.mode in seen[t.city_id]:
                self.error(table.file, row.line, "mode", "duplicate_id", f"second {t.mode} row for {t.city_id}")
            seen[t.city_id].add(t.mode)
        if not table.readable:
            return
        broken = self.broken_cities(table)
        for city in self.expected:
            for mode in rules.LOCAL_MODES:
                if city not in broken and mode not in seen.get(city, set()):
                    self.error(table.file, "-", "mode", "missing_row", f"{city} has no {mode} row")

    def check_matrices(self, hubs, attraction_ids, hotel_ids) -> None:
        for city in self.expected:
            rel = f"{rules.MATRICES_DIR}/{city}.json"
            data, issues = read_json(self.data, rel)
            self.issues += issues
            if data is None:
                continue
            try:
                m = Matrix.model_validate(data)
            except ValidationError as exc:
                for err in exc.errors():
                    self.error(rel, "-", ".".join(map(str, err["loc"])) or "-", "bad_matrix", err["msg"])
                continue
            if m.city_id != city:
                self.error(rel, "-", "city_id", "wrong_file", f"matrix for {m.city_id} in {city} file")
            if m.profile != rules.MATRIX_PROFILE:
                self.error(rel, "-", "profile", "bad_enum", f"profile must be {rules.MATRIX_PROFILE}, got {m.profile!r}")
            try:
                if date.fromisoformat(m.computed_on) > date.today():
                    self.error(rel, "-", "computed_on", "future_date", f"{m.computed_on} is in the future")
            except ValueError:
                self.error(rel, "-", "computed_on", "bad_date", f"must be YYYY-MM-DD, got {m.computed_on!r}")

            # Node kinds whose source file could not be read are not checked, to avoid knock-on errors.
            expected: set[str] = set()
            unchecked: list[str] = []
            if hotel_ids is None:
                unchecked.append(rules.HOTEL_ID_PATTERN)
            else:
                expected |= set(hotel_ids.get(city, []))
            if attraction_ids.get(city) is None:
                unchecked.append(rules.ATTRACTION_ID_PATTERN)
            else:
                expected |= set(attraction_ids[city])
            if hubs is None:
                unchecked.append(rules.HUB_NODE_PATTERN)
            else:
                expected |= {rules.HUB_NODE_FORMAT.format(city=city, mode=mode) for mode in hubs.get(city, set())}
            counts = Counter(m.nodes)
            extra = {node for node in counts.keys() - expected if not any(re.match(p, node) for p in unchecked)}
            for node, n in counts.items():
                if n > 1:
                    self.error(rel, "-", "nodes", "duplicate_id", f"node {node} listed {n} times")
            for node in sorted(expected - counts.keys()):
                self.error(rel, "-", "nodes", "matrix_missing_node", f"node {node} is missing")
            for node in sorted(extra):
                self.error(rel, "-", "nodes", "matrix_extra_node", f"node {node} is not a hotel, attraction or hub of {city}")

            n = len(m.nodes)
            for name, grid in (("km", m.km), ("minutes_free_flow", m.minutes_free_flow)):
                if len(grid) != n or any(len(r) != n for r in grid):
                    self.error(rel, "-", name, "matrix_shape", f"must be {n}×{n}, matching nodes")
                    continue
                for i in range(n):
                    if grid[i][i] != 0:
                        self.error(rel, "-", f"{name}[{i}][{i}]", "matrix_diagonal", f"diagonal must be 0, got {grid[i][i]}")
                bad = [(i, j) for i in range(n) for j in range(n) if i != j and grid[i][j] <= 0]
                if bad:
                    i, j = bad[0]
                    self.error(rel, "-", f"{name}[{i}][{j}]", "matrix_nonpositive",
                               f"{len(bad)} off-diagonal value(s) not positive, first {m.nodes[i]}→{m.nodes[j]} = {grid[i][j]}")


def _sort_key(issue: Issue):
    row = int(issue.row) if issue.row.isdigit() else 0
    return (issue.severity != "error", issue.file, row, issue.field, issue.code)


def validate(data_dir: Path = DEFAULT_DATA, cities: list[str] | None = None) -> list[Issue]:
    return Validator(data_dir, cities).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m datatools.validate", description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="dataset directory (default: data/curated)")
    parser.add_argument("--cities", help="comma-separated city codes to expect instead of all 15 (test fixtures only)")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cities = [c.strip() for c in args.cities.split(",") if c.strip()] if args.cities else None
    issues = validate(args.data, cities)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    for issue in errors:
        print(issue)
    for issue in warnings:
        print(f"warning: {issue}")
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
