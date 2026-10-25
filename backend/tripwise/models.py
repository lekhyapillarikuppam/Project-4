"""Request and response schemas (002 Spec §3, §8; addendum A4, A6; ENG-FR-05, ENG-FR-06)."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Tag = Literal["nature", "adventure", "food", "history", "culture", "spiritual", "shopping", "relaxation", "nightlife"]
TAGS = ("nature", "adventure", "food", "history", "culture", "spiritual", "shopping", "relaxation", "nightlife")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Prefs(Strict):
    daily_hours_out: float = Field(9, ge=4, le=14)
    interests: dict[Tag, int]
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    comfort: Literal["budget", "mid", "premium"] = "mid"
    modes: dict[Literal["train", "bus", "flight"], Literal["preferred", "neutral", "avoid"]] = {}
    avoid_crowds: bool = False


class TripRequest(Strict):
    origin: str
    destination: str
    start_date: date
    end_date: date
    people: int = Field(ge=1, le=6)
    budget_total: int = Field(gt=0)
    prefs: Prefs
    locks: list[str] = []
    excludes: list[str] = []

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def request_hash(self) -> str:
        body = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(body.encode()).hexdigest()

    def mode_pref(self, mode: str) -> str:
        return self.prefs.modes.get(mode, "neutral")


class Outbound(Strict):
    mode: str
    class_: str = Field(alias="class", serialization_alias="class")
    depart: str
    arrive_centre: str
    minutes: int
    overnight: bool
    cost: int
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Return(Strict):
    mode: str
    class_: str = Field(alias="class", serialization_alias="class")
    leave_centre: str
    arrive_origin: str
    minutes: int
    overnight: bool
    cost: int
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Transport(Strict):
    outbound: Outbound
    return_: Return = Field(alias="return", serialization_alias="return")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HotelOut(Strict):
    hotel_id: str
    name: str
    tier: str
    nights: int
    rooms: int
    price_per_room_night: int
    cost: int


class Leg(Strict):
    from_: Optional[str] = Field(None, alias="from", serialization_alias="from")
    to: Optional[str] = None
    minutes: int
    km: float
    mode: str
    cost: int
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Stop(Strict):
    attraction_id: str
    name: str
    arrive: str
    start: str
    end: str
    entry_cost: int
    leg_from_prev: Leg


class Day(Strict):
    day: int
    date: str
    weekday: int
    window: Optional[list[str]]          # None: no window long enough for activities
    lunch: Optional[list[str]]
    stops: list[Stop]
    return_leg: Optional[Leg]


class Budget(Strict):
    outbound: int
    return_: int = Field(alias="return", serialization_alias="return")
    stay: int
    food: int
    entry_fees: int
    local_travel: int
    total: int
    usable_budget: int
    contingency: int
    budget_total: int
    estimate_label: str
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NearMiss(Strict):
    attraction_id: str
    name: str
    reason: Literal["budget", "time", "closed"]


class SolverInfo(Strict):
    hotel_candidates: int
    feedback_iters: int
    repairs: int
    solve_ms: int


class Plan(Strict):
    status: Literal["ok"] = "ok"
    variant: Optional[Literal["experience", "balanced", "saver"]] = None
    dataset_version: str
    request_hash: str
    value: float
    transport: Transport
    hotel: HotelOut
    days: list[Day]
    budget: Budget
    near_misses: list[NearMiss]
    solver: SolverInfo

    def activity_ids(self) -> list[str]:
        return [s.attraction_id for d in self.days for s in d.stops]


class Infeasible(Strict):
    status: Literal["infeasible"] = "infeasible"
    reason: Literal["budget", "no_route", "lock_impossible", "lock_over_budget"]
    min_budget_total: Optional[int] = None
    message: str
    attraction_id: Optional[str] = None      # for lock_impossible


class InternalError(Strict):
    status: Literal["error"] = "error"
    reason: Literal["internal_validation_failed"] = "internal_validation_failed"
    failures: list[str]


class Dropped(Strict):
    name: Literal["experience", "balanced", "saver"]
    reason: str


class VariantsResult(Strict):
    status: Literal["ok"] = "ok"
    variants: list[Plan]
    dropped: list[Dropped]


class TradeOffRow(Strict):
    factor: float
    budget_total: int
    status: str                          # ok or an infeasible reason
    delta_cost: Optional[int] = None
    delta_value: Optional[float] = None
    added: list[str] = []
    dropped: list[str] = []
    hotel_change: Optional[list[str]] = None        # [from hotel_id, to hotel_id]
    transport_change: Optional[list[str]] = None    # [from "mode class / mode class", to …]


class TradeOffs(Strict):
    status: Literal["ok"] = "ok"
    variant: Literal["experience", "balanced", "saver"]
    budget_total: int
    cost: int
    value: float
    rows: list[TradeOffRow]


def dump(model: BaseModel) -> dict:
    return model.model_dump(mode="json", by_alias=True)
