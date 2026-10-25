"""Stage 2 — scheduling with OR-Tools routing, then an exact forward pass (002 Spec §7.4; ENG-FR-04).

Routing (one vehicle per active day, depot = hotel) decides each stop's day and order under time windows,
closed days, the pace count, the span bound U_d (which leaves the lunch hour free) and drop penalties. The forward pass then fixes the times:
the first departure is timed to arrive at the first stop's start, start = max(arrive, open), and lunch is
placed at the hotel before leaving, at a stop before its visit, or at the hotel after returning,
whichever lets the day finish earliest. A day the pass cannot fit drops its lowest-value stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from tripwise.config import Config, hhmm
from tripwise.data import Attraction, Dataset, Hotel
from tripwise.models import TripRequest
from tripwise.timemodel import Window


@dataclass
class StopTime:
    attraction: Attraction
    leg_minutes: int
    leg_km: float
    arrive: int
    start: int
    end: int


@dataclass
class DaySchedule:
    window: Window
    stops: list = field(default_factory=list)       # [StopTime]
    return_minutes: int = 0
    return_km: float = 0.0
    lunch: tuple | None = None                       # (start, end)

    @property
    def depart(self) -> int | None:
        return self.stops[0].arrive - self.stops[0].leg_minutes if self.stops else None

    @property
    def back(self) -> int | None:
        return self.stops[-1].end + self.return_minutes if self.stops else None


def schedule_day(ds: Dataset, cfg: Config, city: str, hotel: Hotel, w: Window, order: list) -> DaySchedule | None:
    """Exact times for one day's ordered stops, or None if they cannot fit."""
    lc = cfg.lunch
    le_min, ll_max, lmin = hhmm(lc["earliest"]), hhmm(lc["latest"]), lc["minutes"]
    if not order:
        lunch = None
        if w.lunch:
            ls = max(w.start, le_min)
            lunch = (ls, ls + lmin)
        return DaySchedule(w, [], 0, 0.0, lunch)
    if not w.active or len(order) > w.max_count:
        return None
    legs = []
    prev = hotel.hotel_id
    for a in order:
        legs.append(ds.travel(city, prev, a.attraction_id))
        prev = a.attraction_id
    back_km, back_min = ds.travel(city, prev, hotel.hotel_id)
    positions = list(range(len(order) + 2)) if w.lunch else [None]
    best = None
    for p in positions:
        cur = w.start
        lunch = None
        if p == 0:
            ls = max(cur, le_min)
            if ls > ll_max:
                continue
            lunch = (ls, ls + lmin)
            cur = ls + lmin
        stops, ok = [], True
        for k, (a, (km, mins)) in enumerate(zip(order, legs), start=1):
            if k == 1:
                target = a.open - mins           # leave so as to arrive at opening, not before the window
                cur = max(cur, target)
            arrive = cur + mins
            earliest = arrive
            if p == k:
                ls = max(arrive, le_min)
                if ls > ll_max:
                    ok = False
                    break
                lunch = (ls, ls + lmin)
                earliest = ls + lmin
            start = max(earliest, a.open)
            if a.fixed_slot and start != a.open:
                ok = False
                break
            end = start + a.visit
            if end > a.close:
                ok = False
                break
            stops.append(StopTime(a, mins, km, arrive, start, end))
            cur = end
        if not ok:
            continue
        back = cur + back_min
        if p == len(order) + 1:
            ls = max(back, le_min)
            if ls > ll_max or ls + lmin > w.end:
                continue
            lunch = (ls, ls + lmin)
        depart = stops[0].arrive - stops[0].leg_minutes
        if depart < w.start or back > w.end:
            continue
        span = back - depart - (lmin if lunch and depart <= lunch[0] and lunch[1] <= back else 0)
        if span > w.usable:
            continue
        if lunch and lunch[1] > w.end:
            continue
        if best is None or back < best[0]:
            best = (back, DaySchedule(w, stops, back_min, back_km, lunch))
    return best[1] if best else None


@dataclass
class Routed:
    days: list            # [DaySchedule] for every trip day, in order
    dropped: list         # [Attraction] chosen in stage 1 but not scheduled


def route(ds: Dataset, cfg: Config, req: TripRequest, hotel: Hotel, windows: list, chosen: list, v: dict) -> Routed:
    city = req.destination
    locks = set(req.fixed_ids())
    active = [w for w in windows if w.active]
    # nodes no active day can take are dropped up front (an empty allowed-vehicle list means "any" to OR-Tools);
    # a pinned attraction (007) may go only on its day
    allowed = {a.attraction_id: [i for i, w in enumerate(active) if w.weekday not in a.closed
                                 and (a.attraction_id not in req.pins or w.day == req.pins[a.attraction_id])]
               for a in chosen}
    nodes = [a for a in chosen if allowed[a.attraction_id]]
    dropped = [a for a in chosen if not allowed[a.attraction_id]]
    assign: dict[int, list] = {i: [] for i in range(len(active))}
    if nodes and active:
        ids = [hotel.hotel_id] + [a.attraction_id for a in nodes]
        visit = [0] + [a.visit for a in nodes]
        n = len(ids)
        travel = [[0 if i == j else ds.travel(city, ids[i], ids[j])[1] for j in range(n)] for i in range(n)]
        mgr = pywrapcp.RoutingIndexManager(n, len(active), 0)
        rt = pywrapcp.RoutingModel(mgr)

        # node-indexed matrices registered in C++ (no Python callbacks in the search loop)
        t_cb = rt.RegisterTransitMatrix([[visit[i] + travel[i][j] for j in range(n)] for i in range(n)])
        rt.SetArcCostEvaluatorOfAllVehicles(rt.RegisterTransitMatrix(travel))
        rt.AddDimension(t_cb, 1440, 1440, False, "time")
        tdim = rt.GetDimensionOrDie("time")
        c_cb = rt.RegisterUnaryTransitVector([0] + [1] * (n - 1))
        rt.AddDimensionWithVehicleCapacity(c_cb, 0, [w.max_count for w in active], True, "count")
        # Lunch is not a routing break (breaks slow the search 25-50x): the span bound U_d already leaves
        # the lunch hour free, and the exact pass places lunch (Changelog 2026-10-25).
        for vi, w in enumerate(active):
            tdim.CumulVar(rt.Start(vi)).SetRange(w.start, w.end)
            tdim.CumulVar(rt.End(vi)).SetRange(w.start, w.end)
            tdim.SetSpanUpperBoundForVehicle(w.usable, vi)
        for k, a in enumerate(nodes, start=1):
            idx = mgr.NodeToIndex(k)
            hi = a.open if a.fixed_slot else a.close - a.visit
            tdim.CumulVar(idx).SetRange(a.open, max(a.open, hi))
            rt.VehicleVar(idx).SetValues([-1] + allowed[a.attraction_id])   # -1: dropped
            if a.attraction_id not in locks:
                rt.AddDisjunction([idx], round(1000 * v[a.attraction_id]))
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        params.local_search_metaheuristic = getattr(routing_enums_pb2.LocalSearchMetaheuristic, cfg.routing_metaheuristic)
        if cfg.routing_solution_limit:
            params.solution_limit = cfg.routing_solution_limit
        params.time_limit.FromMilliseconds(int(cfg.routing_time_limit_s * 1000))
        sol = rt.SolveWithParameters(params)
        if sol is None:
            dropped += nodes
        else:
            for vi in range(len(active)):
                idx = rt.Start(vi)
                while not rt.IsEnd(idx):
                    node = mgr.IndexToNode(idx)
                    if node:
                        assign[vi].append(nodes[node - 1])
                    idx = sol.Value(rt.NextVar(idx))
            placed = {a.attraction_id for s in assign.values() for a in s}
            dropped += [a for a in nodes if a.attraction_id not in placed]
    elif nodes:
        dropped += nodes
    days, ai = [], 0
    for w in windows:
        order = []
        if w.active:
            order = assign[ai]
            ai += 1
        sched = schedule_day(ds, cfg, city, hotel, w, order)
        while sched is None:     # routing and the exact pass disagree: drop the day's lowest-value stop
            removable = [a for a in order if a.attraction_id not in locks] or order
            worst = min(removable, key=lambda a: (v[a.attraction_id], a.attraction_id))
            order = [a for a in order if a is not worst]
            dropped.append(worst)
            sched = schedule_day(ds, cfg, city, hotel, w, order)
        days.append(sched)
    return Routed(days, sorted(dropped, key=lambda a: a.attraction_id))
