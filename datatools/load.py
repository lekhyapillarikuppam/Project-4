"""Load the curated dataset into Neon Postgres (001 Spec §6.7, Plan §3, T22).

    python -m datatools.load [--data DIR] [--schema ref] [--cities JAI,AGR]

1. Run the validator and stop on any error.
2. Open one transaction, create the tables if needed (datatools/sql/schema.sql) and TRUNCATE them.
3. Bulk insert in dependency order (COPY), city pairs expanded to both directions, matrices long-form.
4. Insert the data_version row from data/curated/VERSION, then commit.

Any exception rolls the whole transaction back, so the database keeps its previous data (DATA-FR-11).
`--schema` loads into another schema (the rollback test uses `ref_test`, DATA-AT-04).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from datatools import rules
from datatools.validate import DEFAULT_DATA, validate

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = Path(__file__).parent / "sql" / "schema.sql"
TABLES = ["travel_matrix", "attractions", "hotels", "local_transport", "city_pairs", "hubs", "fare_rates", "food",
          "data_version", "cities"]   # children first, for TRUNCATE
BOOL = {"true": True, "false": False}


def connect() -> psycopg.Connection:
    load_dotenv(ROOT / ".env")
    return psycopg.connect(os.environ["DATABASE_URL"])


def schema_sql(schema: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise ValueError(f"bad schema name {schema!r}")
    return re.sub(r"\bref\b(?=[.;\s])", schema, SCHEMA_SQL.read_text(encoding="utf-8"))


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _cell(col: str, v: str):
    if v == "":
        return [] if col in ("closed_weekdays", "tags") else None
    if v in BOOL:
        return BOOL[v]
    if col == "closed_weekdays":
        return [int(x) for x in v.split(";")]
    if col == "tags":
        return v.split(";")
    return v


def table_rows(data: Path, cities: list[str]) -> dict[str, tuple[list[str], list[list]]]:
    """table -> (columns, rows), in insert order."""
    out: dict[str, tuple[list[str], list[list]]] = {}

    def simple(table: str, rel: str) -> None:
        rows = _rows(data / rel)
        cols = list(rows[0].keys())
        out[table] = (cols, [[_cell(c, r[c]) for c in cols] for r in rows])

    simple("cities", rules.CITIES_FILE)
    simple("fare_rates", rules.FARES_FILE)
    simple("food", rules.FOOD_FILE)
    simple("hubs", rules.HUBS_FILE)
    pairs = _rows(data / rules.PAIRS_FILE)
    cols = ["from_city", "to_city"] + [c for c in pairs[0] if c not in ("city_a", "city_b")]
    expanded = []
    for r in pairs:
        rest = [_cell(c, r[c]) for c in cols[2:]]
        expanded += [[r["city_a"], r["city_b"], *rest], [r["city_b"], r["city_a"], *rest]]
    out["city_pairs"] = (cols, expanded)
    simple("local_transport", rules.LOCAL_FILE)
    simple("hotels", rules.HOTELS_FILE)
    acols, arows = None, []
    for city in cities:
        rows = _rows(data / rules.ATTRACTIONS_DIR / f"{city}.csv")
        acols = list(rows[0].keys())
        arows += [[_cell(c, r[c]) for c in acols] for r in rows]
    out["attractions"] = (acols, arows)
    mrows = []
    for city in cities:
        m = json.loads((data / rules.MATRICES_DIR / f"{city}.json").read_text(encoding="utf-8"))
        for i, a in enumerate(m["nodes"]):
            for j, b in enumerate(m["nodes"]):
                mrows.append([city, a, b, m["km"][i][j], m["minutes_free_flow"][i][j]])
    out["travel_matrix"] = (["city_id", "from_node", "to_node", "km", "minutes_free_flow"], mrows)
    return out


def read_version(data: Path) -> dict[str, str]:
    lines = (data / rules.VERSION_FILE).read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def load(data: Path = DEFAULT_DATA, schema: str = "ref", cities: list[str] | None = None,
         check: bool = True, conn: psycopg.Connection | None = None) -> dict[str, int]:
    """Reload `schema` from `data` in one transaction; returns rows inserted per table.

    `check=False` skips the validator; only the rollback test uses it, to reach a database error."""
    cities = cities or list(rules.CITY_CODES)
    if check:
        errors = [i for i in validate(data, cities if cities != list(rules.CITY_CODES) else None) if i.severity == "error"]
        if errors:
            raise SystemExit(f"validator found {len(errors)} errors; nothing loaded (run python -m datatools.validate)")
    tables = table_rows(data, cities)
    version = read_version(data)
    own = conn is None
    conn = conn or connect()
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(schema_sql(schema))
            cur.execute("TRUNCATE " + ", ".join(f"{schema}.{t}" for t in TABLES))
            for table, (cols, rows) in tables.items():
                with cur.copy(f"COPY {schema}.{table} ({', '.join(cols)}) FROM STDIN") as cp:
                    for row in rows:
                        cp.write_row(row)
            cur.execute(f"INSERT INTO {schema}.data_version (version, compiled) VALUES (%s, %s)",
                        (version["version"], version["compiled"]))
    finally:
        if own:
            conn.close()
    return {t: len(r) for t, (_, r) in tables.items()} | {"data_version": 1}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m datatools.load", description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--schema", default="ref")
    ap.add_argument("--cities", help="comma-separated city codes (test fixtures only)")
    args = ap.parse_args(argv)
    cities = [c.strip() for c in args.cities.split(",")] if args.cities else None
    counts = load(args.data, args.schema, cities)
    for t, n in counts.items():
        print(f"{args.schema}.{t}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
