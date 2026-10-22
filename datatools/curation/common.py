"""Shared helpers for the curation scripts."""

from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CURATED = ROOT / "data" / "curated"
EVIDENCE = RAW / "evidence" / "pages.csv"

USD_INR = 94.593871
USD_INR_SRC = "https://open.er-api.com/v6/latest/USD (INR 94.593871, updated 2026-10-22 00:02 UTC)"
USD_INR_FETCHED = "2026-10-23"


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def fetched_on() -> dict[str, str]:
    """URL -> fetch date, from the evidence log."""
    return {r["url"]: r["fetched_on"] for r in read_csv(EVIDENCE)}


def latest(*dates: str) -> str:
    """checked_on for a derived value: the latest fetch date of its inputs (001 Spec §3)."""
    return max(d for d in dates if d)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))
