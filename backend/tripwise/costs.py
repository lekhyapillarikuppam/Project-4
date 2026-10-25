"""Cost model (002 Spec §5; ENG-FR-02). All amounts are integer rupees."""

from __future__ import annotations

import math

from tripwise.config import Config
from tripwise.data import Dataset, Hotel, round_half_up
from tripwise.models import TripRequest
from tripwise.timemodel import Option


def usable_budget(budget_total: int, cfg: Config) -> int:
    return math.floor(budget_total * cfg.usable_budget_share)


def local_mode(req: TripRequest, cfg: Config) -> str:
    return cfg.local_mode[req.prefs.comfort]


def vehicles(people: int, capacity: int) -> int:
    return math.ceil(people / capacity)


def fare(ds: Dataset, opt: Option) -> int:
    """Per person, one way: max(min_fare, base_fare + per_km × distance), rounded half up."""
    f = ds.fares[(opt.mode, opt.cls)]
    return max(f.min_fare, round_half_up(f.base_fare + f.per_km * opt.km))


def journey(ds: Dataset, cfg: Config, req: TripRequest, opt: Option) -> int:
    """P × fare + destination-side hub access cost × vehicles of the local mode."""
    cap = ds.local[(req.destination, local_mode(req, cfg))].capacity
    return req.people * fare(ds, opt) + opt.dest_hub.access_cost * vehicles(req.people, cap)


def rooms(people: int) -> int:
    return math.ceil(people / 2)


def stay(req: TripRequest, hotel: Hotel) -> int:
    return (req.days - 1) * rooms(req.people) * hotel.price


def food(ds: Dataset, req: TripRequest) -> int:
    return round_half_up(req.people * req.days * ds.food[req.prefs.comfort]
                         * ds.cities[req.destination].food_multiplier)


def entry(req: TripRequest, fee: int) -> int:
    return req.people * fee


def ride(ds: Dataset, cfg: Config, req: TripRequest, km: float) -> int:
    """One local ride: round_half_up(min_fare + per_km × max(0, km − min_km)) × vehicles (001 Spec §5.8)."""
    lt = ds.local[(req.destination, local_mode(req, cfg))]
    return round_half_up(lt.min_fare + lt.per_km * max(0.0, km - lt.min_km)) * vehicles(req.people, lt.capacity)


def est_local(ds: Dataset, cfg: Config, req: TripRequest, km_one_way: float) -> int:
    """Stage 1 estimate for one activity: ride_cost(chain_factor × 2 × km(hotel, a))."""
    return ride(ds, cfg, req, cfg.chain_factor * 2 * km_one_way)


def contingency(budget_total: int, cfg: Config) -> int:
    return budget_total - usable_budget(budget_total, cfg)
