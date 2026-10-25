"""DATA-AT-04: the loader is all-or-nothing (DATA-FR-11).

Runs against a throwaway schema `ref_test` in the Neon database named by DATABASE_URL (001 Plan §6);
the schema is dropped afterwards and `ref` is never touched. Skipped when DATABASE_URL is not set.
"""

import os
import shutil
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from datatools import load as loader
from datatools.tests.test_validate import CITIES, VALID, set_cell

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
SCHEMA = "ref_test"
pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


def counts(conn) -> dict[str, int]:
    with conn.cursor() as cur:
        out = {}
        for t in loader.TABLES:
            cur.execute(f"SELECT count(*) FROM {SCHEMA}.{t}")
            out[t] = cur.fetchone()[0]
        return out


@pytest.fixture
def conn():
    c = loader.connect()
    c.autocommit = True
    yield c
    c.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    c.close()


def test_failed_load_keeps_previous_contents(conn, tmp_path):
    inserted = loader.load(VALID, SCHEMA, CITIES, conn=conn)
    before = counts(conn)
    assert before == inserted

    broken = tmp_path / "data"
    shutil.copytree(VALID, broken)
    # The validator would reject this row; skipping it lets the bad row reach the database (foreign key).
    set_cell(broken / "hotels.csv", "hotel_id", "AGR-H-05", "city_id", "XYZ")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        loader.load(broken, SCHEMA, CITIES, check=False, conn=conn)
    assert counts(conn) == before
