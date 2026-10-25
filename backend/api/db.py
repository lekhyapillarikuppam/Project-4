"""Postgres access (004 Plan): psycopg 3 with a connection pool and small query helpers; no ORM.

Every query names its schema (`{s}.table`): Neon's pooled endpoint runs PgBouncer in transaction mode,
where a session `SET search_path` does not stick and server-side prepared statements are unsafe.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from api import settings
from tripwise import config

SCHEMA_SQL = Path(__file__).parent / "sql" / "app_schema.sql"
_pool: ConnectionPool | None = None


def schema() -> str:
    return settings.get().db_schema


def _configure(conn: psycopg.Connection) -> None:
    conn.prepare_threshold = None     # no server-side prepared statements behind PgBouncer


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        size = config.default().api["db_pool"]
        _pool = ConnectionPool(settings.get().database_url, min_size=size["min"], max_size=size["max"],
                               kwargs={"row_factory": dict_row, "autocommit": True}, configure=_configure, open=True)
    return _pool


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def q(sql: str) -> str:
    """Fill the schema into `{s}` placeholders."""
    return sql.replace("{s}", schema())


def one(sql: str, *args: Any) -> dict | None:
    with pool().connection() as conn:
        return conn.execute(q(sql), args).fetchone()


def all_(sql: str, *args: Any) -> list[dict]:
    with pool().connection() as conn:
        return conn.execute(q(sql), args).fetchall()


def run(sql: str, *args: Any) -> int:
    with pool().connection() as conn:
        return conn.execute(q(sql), args).rowcount


def jsonb(x: Any) -> Jsonb:
    return Jsonb(x)


def create_schema(name: str | None = None) -> None:
    name = name or schema()
    sql = re.sub(r"\bapp\b(?=[.;\s])", name, SCHEMA_SQL.read_text(encoding="utf-8"))
    with psycopg.connect(settings.get().database_url, autocommit=True) as conn:
        conn.prepare_threshold = None
        conn.execute(sql)


def drop_schema(name: str) -> None:
    """Drop a test schema. Refuses anything not ending in _test."""
    if not name.endswith("_test"):
        raise RuntimeError(f"refusing to drop non-test schema {name!r}")
    with psycopg.connect(settings.get().database_url, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
