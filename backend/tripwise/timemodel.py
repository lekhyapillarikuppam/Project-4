"""Time model (002 Spec §4; ENG-FR-01): transport options, journey times, day windows, lunch, U_d."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta

from tripwise.config import Config, hhmm
from tripwise.data import Dataset, Hub
from tripwise.models import TripRequest


@dataclass(frozen=True)
class Option:
    """One transport option (a fare row of an available mode) in one direction."""
    direction: str            # "out" or "ret"
    mode: str
    cls: str
    mode_minutes: int
    km: float
    overnight: bool
    comfort: float
    preferred: bool
    dest_hub: Hub             # the hub at the trip's destination city
    origin_hub: Hub           # the hub at the trip's origin city

    @property
    def key(self) -> str:
        return f"{self.mode} {self.cls}"


def options(ds: Dataset, cfg: Config, req: TripRequest, direction: str) -> list[Option]:
    """Options for the outbound (origin → destination) or return journey, after §4.2 removals."""
    a, b = (req.origin, req.destination) if direction == "out" else (req.destination, req.origin)
    pair = ds.pairs.get((a, b))
    out: list[Option] = []
    if pair is None:
        return out
    for mode in ("train", "bus", "flight"):
        if req.mode_pref(mode) == "avoid" or not pair.available[mode]:
            continue
        minutes = pair.minutes[mode]
        dest_hub = ds.hubs.get((req.destination, mode))
        origin_hub = ds.hubs.get((req.origin, mode))
        if minutes is None or dest_hub is None or origin_hub is None:
            continue
        if mode != "flight" and minutes > cfg.max_surface_minutes:
            continue
        overnight = mode != "flight" and minutes >= cfg.overnight_min_minutes
        for f in ds.fare_classes(mode):
            out.append(Option(direction, mode, f.cls, minutes, pair.km[mode], overnight, f.comfort_value,
                              req.mode_pref(mode) == "preferred", dest_hub, origin_hub))
    return out


def door_minutes(opt: Option, cfg: Config) -> int:
    """Door-to-door journey time J (§4.2)."""
    return (opt.origin_hub.access_minutes + opt.mode_minutes + opt.dest_hub.access_minutes
            + (cfg.flight_overhead_minutes if opt.mode == "flight" else 0))


def outbound_times(opt: Option, cfg: Config) -> dict:
    """Departure from the origin hub, arrival at the destination centre and the earliest day-1 start (§4.3)."""
    if opt.overnight:
        arrive_hub = hhmm(cfg.overnight_arrive)
        depart = (arrive_hub - opt.mode_minutes) % 1440
        arrive = arrive_hub + opt.dest_hub.access_minutes
        earliest = arrive_hub + opt.dest_hub.access_minutes + cfg.overnight_arrival_buffer_minutes
    else:
        depart = hhmm(cfg.flight_depart if opt.mode == "flight" else cfg.surface_depart)
        arrive = depart + opt.mode_minutes + opt.dest_hub.access_minutes
        earliest = arrive + cfg.arrival_buffer_minutes
    return {"depart": depart, "arrive_centre": arrive, "day1_earliest": earliest}


def return_times(opt: Option, cfg: Config) -> dict:
    """Departure from the destination centre, arrival at the origin hub and the latest day-D end (§4.3)."""
    if opt.overnight:
        leave_hub = hhmm(cfg.overnight_depart)
        leave = leave_hub - opt.dest_hub.access_minutes
        arrive_origin = (leave_hub + opt.mode_minutes) % 1440
        latest = leave_hub - opt.dest_hub.access_minutes - cfg.departure_buffer_minutes
    else:
        overhead = cfg.flight_overhead_minutes if opt.mode == "flight" else 0
        leave = hhmm(cfg.return_deadline) - (opt.mode_minutes + opt.dest_hub.access_minutes + overhead)
        arrive_origin = hhmm(cfg.return_deadline)
        latest = leave - cfg.departure_buffer_minutes
    return {"leave_centre": leave, "arrive_origin": arrive_origin, "dayD_latest": latest}


@dataclass(frozen=True)
class Window:
    day: int                  # 1..D
    date: str
    weekday: int              # 0 = Monday
    start: int
    end: int
    active: bool              # window ≥ min_activity_window_minutes
    lunch: bool
    usable: int               # U_d (0 when not active)
    max_count: int            # pace limit (0 when not active)


def lunch_fits(start: int, end: int, cfg: Config) -> bool:
    """A day gets lunch if its window is ≥ min_window_h and a lunch starting 12:30–14:30 fits inside it."""
    lc = cfg.lunch
    if end - start < lc["min_window_h"] * 60:
        return False
    first = max(start, hhmm(lc["earliest"]))
    return first <= hhmm(lc["latest"]) and first + lc["minutes"] <= end


def make_window(day: int, req: TripRequest, start: int, end: int, cfg: Config) -> Window:
    d = req.start_date + timedelta(days=day - 1)
    active = end - start >= cfg.min_activity_window_minutes
    lunch = active and lunch_fits(start, end, cfg)
    pace = cfg.pace[req.prefs.pace]
    usable = math.floor((end - start - (cfg.lunch["minutes"] if lunch else 0)) * pace["fill"]) if active else 0
    return Window(day, d.isoformat(), d.weekday(), start, end, active, lunch, usable, pace["max"] if active else 0)


def nominal(req: TripRequest, cfg: Config) -> tuple[int, int]:
    s = hhmm(cfg.day_start)
    return s, min(s + round(req.prefs.daily_hours_out * 60), hhmm(cfg.day_end_cap))


def day_windows(req: TripRequest, cfg: Config, out: Option, ret: Option) -> list[Window]:
    s, e = nominal(req, cfg)
    n = req.days
    wins = []
    for d in range(1, n + 1):
        start, end = s, e
        if d == 1:
            start = max(s, outbound_times(out, cfg)["day1_earliest"])
        if d == n:
            end = min(e, return_times(ret, cfg)["dayD_latest"])
        wins.append(make_window(d, req, start, max(start, end), cfg))
    return wins


def first_window(req: TripRequest, cfg: Config, out: Option) -> Window:
    s, e = nominal(req, cfg)
    start = max(s, outbound_times(out, cfg)["day1_earliest"])
    return make_window(1, req, start, max(start, e), cfg)


def last_window(req: TripRequest, cfg: Config, ret: Option) -> Window:
    s, e = nominal(req, cfg)
    end = min(e, return_times(ret, cfg)["dayD_latest"])
    return make_window(req.days, req, s, max(s, end), cfg)


def middle_windows(req: TripRequest, cfg: Config) -> list[Window]:
    s, e = nominal(req, cfg)
    return [make_window(d, req, s, e, cfg) for d in range(2, req.days)]
