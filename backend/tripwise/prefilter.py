"""Pre-filter (002 Spec §7.1; ENG-FR-04).

An attraction is dropped if it is excluded, closed on every trip day, or its opening interval cannot hold
its visit inside any day's window. Windows are taken at their widest over the transport options, so the
filter never drops an attraction that some option could schedule.
"""

from __future__ import annotations

from dataclasses import dataclass

from tripwise.config import Config
from tripwise.data import Attraction, Dataset
from tripwise.models import TripRequest
from tripwise.timemodel import Option, Window, first_window, last_window, middle_windows


def fits(a: Attraction, w: Window) -> bool:
    """The visit can lie inside both the window and the opening interval on that day."""
    if not w.active or w.weekday in a.closed:
        return False
    if a.fixed_slot:
        return w.start <= a.open and a.open + a.visit <= min(a.close, w.end)
    return max(a.open, w.start) + a.visit <= min(a.close, w.end)


def widest_windows(req: TripRequest, cfg: Config, outs: list[Option], rets: list[Option]) -> list[Window]:
    firsts = [first_window(req, cfg, o) for o in outs]
    lasts = [last_window(req, cfg, r) for r in rets]
    day1 = min(firsts, key=lambda w: (w.start, -w.end))
    dayn = max(lasts, key=lambda w: (w.end, -w.start))
    return [day1] + middle_windows(req, cfg) + [dayn]


@dataclass
class Filtered:
    kept: list            # [Attraction] in file order
    removed: dict         # attraction_id -> "excluded" | "closed"
    lock_problem: str | None   # attraction_id of an impossible lock
    pin_problem: str | None = None   # attraction_id of an impossible pin (007)


def prefilter(ds: Dataset, cfg: Config, req: TripRequest, outs: list[Option], rets: list[Option]) -> Filtered:
    wins = widest_windows(req, cfg, outs, rets)
    kept, removed = [], {}
    for a in ds.by_city[req.destination]:
        if a.attraction_id in req.excludes:
            removed[a.attraction_id] = "excluded"
        elif not any(fits(a, w) for w in wins):
            removed[a.attraction_id] = "closed"
        else:
            kept.append(a)
    problem = None
    for lid in req.locks:
        at = ds.attractions.get(lid)
        if at is None or at.city_id != req.destination or lid in removed:
            problem = lid
            break
    pin_problem = None
    for pid, day in req.pins.items():
        at = ds.attractions.get(pid)
        if at is None or at.city_id != req.destination or pid in removed or not 1 <= day <= req.days                 or not fits(at, wins[day - 1]):
            pin_problem = pid
            break
    return Filtered(kept, removed, problem, pin_problem)
