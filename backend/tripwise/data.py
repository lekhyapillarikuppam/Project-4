"""The curated dataset in memory (002 Plan §1; ENG-FR-02).

The engine reads data/curated/ (Feature 001) once into a `Dataset`. City pairs are expanded to both
directions; matrix times are multiplied by the city's traffic factor and rounded half up to minutes.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

MODES = ("train", "bus", "flight")
TIERS = ("budget", "mid", "premium")


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def _hhmm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


@dataclass(frozen=True)
class City:
    city_id: str
    name: str
    lat: float
    lon: float
    traffic_factor: float
    food_multiplier: float


@dataclass(frozen=True)
class Hub:
    city_id: str
    mode: str
    hub_name: str
    hub_code: str
    access_km: float
    access_minutes: int
    access_cost: int


@dataclass(frozen=True)
class Pair:
    from_city: str
    to_city: str
    km: dict            # mode -> distance used by its fare (rail_km, road_km, air_km)
    available: dict     # mode -> bool
    minutes: dict       # mode -> int | None


@dataclass(frozen=True)
class Fare:
    mode: str
    cls: str
    base_fare: int
    per_km: float
    min_fare: int
    comfort_value: float


@dataclass(frozen=True)
class Attraction:
    attraction_id: str
    city_id: str
    name: str
    lat: float
    lon: float
    visit: int
    open: int
    close: int
    closed: frozenset
    fee: int
    tags: tuple
    rating: float
    crowd: str
    fixed_slot: bool
    kind: str = ""          # 001 §5.5: church, mosque, temple, fort, beach, … (007 limit_kind)


@dataclass(frozen=True)
class Hotel:
    hotel_id: str
    city_id: str
    name: str
    tier: str
    lat: float
    lon: float
    price: int


@dataclass(frozen=True)
class Local:
    city_id: str
    mode: str
    min_fare: int
    min_km: float
    per_km: float
    capacity: int


@dataclass
class Matrix:
    city_id: str
    index: dict
    km: list
    minutes: list       # already × traffic factor, whole minutes


@dataclass
class Dataset:
    version: str
    compiled: str
    cities: dict = field(default_factory=dict)
    hubs: dict = field(default_factory=dict)          # (city, mode) -> Hub
    pairs: dict = field(default_factory=dict)         # (from, to) -> Pair
    fares: dict = field(default_factory=dict)         # (mode, cls) -> Fare
    attractions: dict = field(default_factory=dict)   # id -> Attraction
    by_city: dict = field(default_factory=dict)       # city -> [Attraction], file order
    hotels: dict = field(default_factory=dict)        # id -> Hotel
    hotels_by: dict = field(default_factory=dict)     # (city, tier) -> [Hotel], file order
    food: dict = field(default_factory=dict)          # comfort -> base per person per day
    local: dict = field(default_factory=dict)         # (city, mode) -> Local
    matrices: dict = field(default_factory=dict)      # city -> Matrix

    @property
    def label(self) -> str:
        return f"{self.version} ({self.compiled})"

    def estimate_label(self) -> str:
        y, m = self.compiled.split("-")
        month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(m) - 1]
        return f"Estimated prices, compiled {month} {y}"

    def travel(self, city: str, a: str, b: str) -> tuple[float, int]:
        """(km, minutes with traffic) between two nodes of a city's matrix."""
        m = self.matrices[city]
        i, j = m.index[a], m.index[b]
        return m.km[i][j], m.minutes[i][j]

    def fare_classes(self, mode: str) -> list:
        return [f for (md, _), f in self.fares.items() if md == mode]


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _bool(v: str) -> bool:
    return v == "true"


def load(data_dir: Path) -> Dataset:
    ver = dict(line.split("=", 1) for line in (data_dir / "VERSION").read_text(encoding="utf-8").splitlines() if "=" in line)
    ds = Dataset(version=ver["version"].strip(), compiled=ver["compiled"].strip())
    for r in _rows(data_dir / "cities.csv"):
        ds.cities[r["city_id"]] = City(r["city_id"], r["name"], float(r["lat"]), float(r["lon"]),
                                       float(r["traffic_factor"]), float(r["food_multiplier"]))
    for r in _rows(data_dir / "hubs.csv"):
        ds.hubs[(r["city_id"], r["mode"])] = Hub(r["city_id"], r["mode"], r["hub_name"], r["hub_code"],
                                                 float(r["access_km"]), int(r["access_minutes"]),
                                                 int(r["access_cost_per_vehicle"]))
    dist = {"train": "rail_km", "bus": "road_km", "flight": "air_km"}
    for r in _rows(data_dir / "city_pairs.csv"):
        km = {m: float(r[dist[m]]) if r[dist[m]] else None for m in MODES}
        avail = {m: _bool(r[f"{m}_available"]) for m in MODES}
        mins = {m: int(r[f"{m}_minutes"]) if r[f"{m}_minutes"] else None for m in MODES}
        for a, b in ((r["city_a"], r["city_b"]), (r["city_b"], r["city_a"])):
            ds.pairs[(a, b)] = Pair(a, b, km, avail, mins)
    for r in _rows(data_dir / "fare_rates.csv"):
        ds.fares[(r["mode"], r["class"])] = Fare(r["mode"], r["class"], int(r["base_fare"]), float(r["per_km"]),
                                                  int(r["min_fare"]), float(r["comfort_value"]))
    for city in ds.cities:
        ds.by_city[city] = []
        for r in _rows(data_dir / "attractions" / f"{city}.csv"):
            a = Attraction(r["attraction_id"], r["city_id"], r["name"], float(r["lat"]), float(r["lon"]),
                           int(r["visit_minutes"]), _hhmm(r["open_time"]), _hhmm(r["close_time"]),
                           frozenset(int(x) for x in r["closed_weekdays"].split(";") if x),
                           int(r["entry_fee"]), tuple(r["tags"].split(";")), float(r["rating"]),
                           r["crowd_level"], _bool(r["fixed_slot"]), r.get("kind", ""))
            ds.attractions[a.attraction_id] = a
            ds.by_city[city].append(a)
    for r in _rows(data_dir / "hotels.csv"):
        h = Hotel(r["hotel_id"], r["city_id"], r["name"], r["tier"], float(r["lat"]), float(r["lon"]),
                  int(r["price_per_room_night"]))
        ds.hotels[h.hotel_id] = h
        ds.hotels_by.setdefault((h.city_id, h.tier), []).append(h)
    for r in _rows(data_dir / "food.csv"):
        ds.food[r["comfort"]] = int(r["base_per_person_per_day"])
    for r in _rows(data_dir / "local_transport.csv"):
        ds.local[(r["city_id"], r["mode"])] = Local(r["city_id"], r["mode"], int(r["min_fare"]), float(r["min_km"]),
                                                    float(r["per_km"]), int(r["capacity"]))
    for city, c in ds.cities.items():
        doc = json.loads((data_dir / "matrices" / f"{city}.json").read_text(encoding="utf-8"))
        tf = c.traffic_factor
        ds.matrices[city] = Matrix(city, {n: i for i, n in enumerate(doc["nodes"])}, doc["km"],
                                   [[round_half_up(x * tf) for x in row] for row in doc["minutes_free_flow"]])
    return ds


@lru_cache(maxsize=4)
def load_cached(data_dir: str) -> Dataset:
    return load(Path(data_dir))


def default() -> Dataset:
    from tripwise import config
    return load_cached(str(config.default().data_dir))
