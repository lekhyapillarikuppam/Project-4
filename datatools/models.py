"""Pydantic row models, one per entity (001 Spec §5).

Two levels of checking:
- Field types and formats are enforced by Pydantic. A row that fails here cannot be
  used by the dataset checks.
- `row_checks()` returns rule problems that need several fields, or that should not
  stop the row being used (provenance, city code, opening hours, price band, ...).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic_core import PydanticCustomError

from datatools import rules
from datatools.io import split_list


class Problem(NamedTuple):
    field: str
    code: str
    message: str


# --- Cell parsers ----------------------------------------------------------

def _parse_bool(value):
    if isinstance(value, bool) or value is None:
        return value
    if value in ("true", "false"):
        return value == "true"
    raise PydanticCustomError("bad_bool", "must be true or false, got {value}", {"value": repr(value)})


def _decimals(places: int):
    def check(value):
        if isinstance(value, str):
            _, _, frac = value.partition(".")
            if len(frac) > places:
                raise PydanticCustomError(
                    "bad_precision", "at most {places} decimal places, got {value}",
                    {"places": places, "value": value},
                )
        return value
    return check


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _parse_time(value):
    """`HH:MM` -> minutes after midnight."""
    if not isinstance(value, str):
        return value
    m = _TIME_RE.match(value)
    if not m:
        raise PydanticCustomError("bad_time", "must be HH:MM (24-hour), got {value}", {"value": repr(value)})
    return int(m.group(1)) * 60 + int(m.group(2))


def _parse_list(value):
    return split_list(value) if isinstance(value, str) or value is None else value


def fmt_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


Bool = Annotated[bool, BeforeValidator(_parse_bool)]
Lat = Annotated[float, Field(ge=-90, le=90), BeforeValidator(_decimals(rules.COORD_DECIMALS))]
Lon = Annotated[float, Field(ge=-180, le=180), BeforeValidator(_decimals(rules.COORD_DECIMALS))]
Km = Annotated[float, Field(ge=0), BeforeValidator(_decimals(rules.KM_DECIMALS))]
PosKm = Annotated[float, Field(gt=0), BeforeValidator(_decimals(rules.KM_DECIMALS))]
Rupees = Annotated[int, Field(ge=0)]
Minutes = Annotated[int, Field(ge=0)]
Time = Annotated[int, BeforeValidator(_parse_time)]
StrList = Annotated[list[str], BeforeValidator(_parse_list)]
Code3 = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


# --- Shared checks ---------------------------------------------------------

def _city_problem(fld: str, city: str) -> list[Problem]:
    if city not in rules.CITY_CODES:
        return [Problem(fld, "unknown_city", f"unknown city code {city!r}")]
    return []


class Curated(BaseModel):
    """Base for every curated row: carries provenance (DATA-FR-08)."""

    model_config = ConfigDict(extra="forbid")

    # Optional at type level so a row with missing provenance is still usable;
    # row_checks() reports the problem.
    source: str | None = None
    checked_on: str | None = None

    def provenance_checks(self) -> list[Problem]:
        out: list[Problem] = []
        if not self.source:
            out.append(Problem("source", "missing_source", "source is required"))
        if not self.checked_on:
            out.append(Problem("checked_on", "missing_checked_on", "checked_on is required"))
        else:
            try:
                d = date.fromisoformat(self.checked_on)
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.checked_on):
                    raise ValueError
            except ValueError:
                out.append(Problem("checked_on", "bad_date", f"must be YYYY-MM-DD, got {self.checked_on!r}"))
            else:
                if d > date.today():
                    out.append(Problem("checked_on", "future_date", f"{self.checked_on} is in the future"))
        return out

    def checks(self) -> list[Problem]:
        return []

    def row_checks(self) -> list[Problem]:
        return self.checks() + self.provenance_checks()


# --- 5.1 cities.csv --------------------------------------------------------

class City(Curated):
    city_id: Code3
    name: str
    lat: Lat
    lon: Lon
    traffic_factor: Annotated[float, Field(ge=rules.TRAFFIC_FACTOR_RANGE[0], le=rules.TRAFFIC_FACTOR_RANGE[1])]
    food_multiplier: Annotated[float, Field(ge=rules.FOOD_MULTIPLIER_RANGE[0], le=rules.FOOD_MULTIPLIER_RANGE[1])]

    def checks(self) -> list[Problem]:
        return _city_problem("city_id", self.city_id)


# --- 5.2 hubs.csv ----------------------------------------------------------

class Hub(Curated):
    city_id: Code3
    mode: Literal["train", "bus", "flight"]
    hub_name: str
    hub_code: str | None = None
    lat: Lat
    lon: Lon
    access_km: Km
    access_minutes: Minutes
    access_cost_per_vehicle: Rupees

    def checks(self) -> list[Problem]:
        return _city_problem("city_id", self.city_id)


# --- 5.3 city_pairs.csv ----------------------------------------------------

def fallback_minutes(km: float, formula: dict) -> int:
    return round(km / formula["speed_kmh"] * 60 + formula["extra_min"])


class CityPair(Curated):
    city_a: Code3
    city_b: Code3
    road_km: PosKm
    rail_km: PosKm
    air_km: PosKm | None = None
    train_available: Bool
    bus_available: Bool
    flight_available: Bool
    train_minutes: Minutes | None = None
    bus_minutes: Minutes | None = None
    flight_minutes: Minutes | None = None
    rail_km_approx: Bool
    train_minutes_approx: Bool
    bus_minutes_approx: Bool
    flight_minutes_approx: Bool

    def available_modes(self) -> list[str]:
        return [m for m in rules.TRANSPORT_MODES if getattr(self, f"{m}_available")]

    def checks(self) -> list[Problem]:
        out = _city_problem("city_a", self.city_a) + _city_problem("city_b", self.city_b)
        if self.city_a >= self.city_b:
            out.append(Problem("city_b", "pair_order",
                               f"city_a must sort before city_b ({self.city_a} >= {self.city_b})"))
        if not self.available_modes():
            out.append(Problem("-", "pair_no_mode", "no transport mode is available"))
        for mode in self.available_modes():
            minutes = getattr(self, f"{mode}_minutes")
            if not minutes:
                out.append(Problem(f"{mode}_minutes", "missing_duration",
                                   f"{mode} is available but has no positive duration"))
        if self.bus_available and self.road_km > rules.BUS_MAX_ROAD_KM:
            out.append(Problem("bus_available", "bus_too_far",
                               f"bus needs road_km <= {rules.BUS_MAX_ROAD_KM}, got {self.road_km}"))
        if self.flight_available:
            if self.air_km is None:
                out.append(Problem("air_km", "missing_value", "flight is available but air_km is missing"))
            elif self.air_km < rules.FLIGHT_MIN_AIR_KM:
                out.append(Problem("flight_available", "flight_too_short",
                                   f"flight needs air_km >= {rules.FLIGHT_MIN_AIR_KM}, got {self.air_km}"))
        if self.rail_km_approx and self.rail_km != self.road_km:
            out.append(Problem("rail_km", "approx_mismatch",
                               f"rail_km_approx is true, so rail_km must equal road_km ({self.rail_km} != {self.road_km})"))
        out += self._fallback_checks()
        return out

    def _fallback_checks(self) -> list[Problem]:
        """A duration flagged as approximate must equal the 5.3 fallback formula."""
        out: list[Problem] = []
        tol = rules.FALLBACK_TOLERANCE_MIN
        cases = [
            ("train", self.rail_km, [fallback_minutes(self.rail_km, rules.TRAIN_FALLBACK)]),
            ("bus", self.road_km, [fallback_minutes(self.road_km, rules.BUS_FALLBACK)]),
        ]
        if self.air_km is not None:
            direct = fallback_minutes(self.air_km, rules.FLIGHT_FALLBACK)
            cases.append(("flight", self.air_km, [direct, direct + rules.FLIGHT_ONE_STOP_EXTRA_MIN]))
        for mode, _, expected in cases:
            minutes = getattr(self, f"{mode}_minutes")
            if getattr(self, f"{mode}_minutes_approx") and minutes is not None:
                if all(abs(minutes - e) > tol for e in expected):
                    want = " or ".join(str(e) for e in expected)
                    out.append(Problem(f"{mode}_minutes", "approx_mismatch",
                                       f"flagged approximate but {minutes} != formula value {want}"))
        return out


# --- 5.4 fare_rates.csv ----------------------------------------------------

class FareRate(Curated):
    mode: Literal["train", "bus", "flight"]
    # `class` is a Python keyword, so the attribute is fare_class with the CSV name as alias.
    fare_class: str = Field(alias="class")
    base_fare: Rupees
    per_km: Annotated[float, Field(ge=0)]
    min_fare: Rupees
    comfort_value: Annotated[float, Field(ge=rules.COMFORT_VALUE_RANGE[0], le=rules.COMFORT_VALUE_RANGE[1])]

    def checks(self) -> list[Problem]:
        key = (self.mode, self.fare_class)
        if key not in rules.FARE_CLASSES:
            return [Problem("class", "bad_enum", f"unknown class {self.fare_class!r} for mode {self.mode}")]
        out: list[Problem] = []
        lo, hi = rules.FARE_CLASSES[key]
        if not lo <= self.per_km <= hi:
            out.append(Problem("per_km", "fare_out_of_bounds",
                               f"{self.fare_class} per_km must be {lo}–{hi}, got {self.per_km}"))
        if key in rules.FARE_BASE_BOUNDS:
            lo, hi = rules.FARE_BASE_BOUNDS[key]
            if not lo <= self.base_fare <= hi:
                out.append(Problem("base_fare", "fare_out_of_bounds",
                                   f"{self.fare_class} base_fare must be {lo}–{hi}, got {self.base_fare}"))
        return out



# --- 5.5 attractions/<CITY>.csv ---------------------------------------------

class Attraction(Curated):
    attraction_id: Annotated[str, Field(pattern=rules.ATTRACTION_ID_PATTERN)]
    city_id: Code3
    name: str
    lat: Lat
    lon: Lon
    visit_minutes: Annotated[int, Field(ge=rules.VISIT_MINUTES_RANGE[0], le=rules.VISIT_MINUTES_RANGE[1])]
    open_time: Time
    close_time: Time
    closed_weekdays: StrList = []
    entry_fee: Rupees
    tags: StrList
    rating: Annotated[float, Field(ge=rules.RATING_RANGE[0], le=rules.RATING_RANGE[1])]
    outdoor: Bool
    crowd_level: Literal["low", "medium", "high"]
    fixed_slot: Bool

    def weekdays(self) -> list[int]:
        return [int(d) for d in self.closed_weekdays]

    def checks(self) -> list[Problem]:
        out = _city_problem("city_id", self.city_id)
        if out:
            return out
        if self.attraction_id[:3] != self.city_id:
            out.append(Problem("attraction_id", "id_city_mismatch",
                               f"{self.attraction_id} does not start with city {self.city_id}"))
        if self.open_time >= self.close_time:
            out.append(Problem("close_time", "open_not_before_close",
                               f"must be later than open_time ({fmt_time(self.open_time)} ≥ {fmt_time(self.close_time)})"))
        elif self.close_time - self.open_time < self.visit_minutes:
            out.append(Problem("visit_minutes", "visit_exceeds_hours",
                               f"{self.visit_minutes} min does not fit in {fmt_time(self.open_time)}–{fmt_time(self.close_time)}"))
        lo_day, hi_day = rules.WEEKDAY_RANGE
        days = self.closed_weekdays
        if any(not d.isdigit() or not lo_day <= int(d) <= hi_day for d in days):
            out.append(Problem("closed_weekdays", "bad_weekday",
                               f"weekdays must be {lo_day}–{hi_day}, got {';'.join(days)}"))
        elif len(set(days)) != len(days):
            out.append(Problem("closed_weekdays", "duplicate_value", "weekday listed twice"))
        lo, hi = rules.TAGS_PER_ATTRACTION
        if not lo <= len(self.tags) <= hi:
            out.append(Problem("tags", "bad_tag_count", f"needs {lo}–{hi} tags, got {len(self.tags)}"))
        bad = [t for t in self.tags if t not in rules.TAGS]
        if bad:
            out.append(Problem("tags", "bad_tag", f"unknown tag(s) {', '.join(bad)}"))
        elif len(set(self.tags)) != len(self.tags):
            out.append(Problem("tags", "duplicate_value", "tag listed twice"))
        return out


# --- 5.6 hotels.csv --------------------------------------------------------

class Hotel(Curated):
    hotel_id: Annotated[str, Field(pattern=rules.HOTEL_ID_PATTERN)]
    city_id: Code3
    name: str
    tier: Literal["budget", "mid", "premium"]
    lat: Lat
    lon: Lon
    price_per_room_night: Rupees

    def checks(self) -> list[Problem]:
        out = _city_problem("city_id", self.city_id)
        if out:
            return out
        if self.hotel_id[:3] != self.city_id:
            out.append(Problem("hotel_id", "id_city_mismatch",
                               f"{self.hotel_id} does not start with city {self.city_id}"))
        lo, hi = rules.PRICE_BANDS[self.tier]
        if not lo <= self.price_per_room_night <= hi:
            out.append(Problem("price_per_room_night", "price_out_of_band",
                               f"{self.tier} must be ₹{lo}–{hi}, got ₹{self.price_per_room_night}"))
        return out


# --- 5.7 food.csv ----------------------------------------------------------

class Food(Curated):
    comfort: Literal["budget", "mid", "premium"]
    base_per_person_per_day: Annotated[int, Field(gt=0)]


# --- 5.8 local_transport.csv -----------------------------------------------

class LocalTransport(Curated):
    city_id: Code3
    mode: Literal["auto", "cab"]
    min_fare: Rupees
    min_km: Annotated[float, Field(ge=0)]
    per_km: Annotated[float, Field(ge=0)]
    capacity: Annotated[int, Field(gt=0)]
    approx: Bool

    def checks(self) -> list[Problem]:
        out = _city_problem("city_id", self.city_id)
        want = rules.LOCAL_CAPACITY[self.mode]
        if self.capacity != want:
            out.append(Problem("capacity", "bad_capacity", f"{self.mode} capacity must be {want}, got {self.capacity}"))
        return out


# --- 5.9 matrices/<CITY>.json ----------------------------------------------

class Matrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city_id: Code3
    profile: str
    computed_on: str
    nodes: list[str]
    km: list[list[float]]
    minutes_free_flow: list[list[int]]

