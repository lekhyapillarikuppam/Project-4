"""Stage 1 — selection with CP-SAT, one model per candidate hotel (002 Spec §7.3, addendum A2; ENG-FR-04).

Objective modes:
- max_value: maximise 1000 × V − cost (cost ≤ B_u)
- balanced:  maximise B_u × 1000 × V − 1000 × λ × V* × cost (cost ≤ B_u)
- min_cost:  minimise cost subject to V ≥ ρ × V* (cost ≤ B_u when a budget is given)
V here uses the stage 1 travel estimate; stage 2 replaces it with the routed value.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from ortools.sat.python import cp_model

from tripwise import costs, value
from tripwise.config import Config
from tripwise.data import Attraction, Dataset, Hotel, round_half_up
from tripwise.models import TripRequest
from tripwise.timemodel import Option, first_window, last_window, middle_windows

SCALE = 1000


@dataclass
class Candidate:
    """Per-request data shared by every hotel's model."""
    req: TripRequest
    outs: list
    rets: list
    attrs: list               # pre-filtered Attraction list
    v: dict                   # attraction_id -> v(a)
    out_cost: list
    ret_cost: list
    u1: list                  # U_1 per outbound option
    c1: list                  # count limit day 1 per outbound option
    ud: list
    cd: list
    u_mid: int
    c_mid: int
    food: int


def prepare(ds: Dataset, cfg: Config, req: TripRequest, outs: list[Option], rets: list[Option], attrs: list) -> Candidate:
    mids = middle_windows(req, cfg)
    f1 = [first_window(req, cfg, o) for o in outs]
    fd = [last_window(req, cfg, r) for r in rets]
    return Candidate(req, outs, rets, attrs, {a.attraction_id: value.activity(a, req.prefs, cfg) for a in attrs},
                     [costs.journey(ds, cfg, req, o) for o in outs], [costs.journey(ds, cfg, req, r) for r in rets],
                     [w.usable for w in f1], [w.max_count for w in f1], [w.usable for w in fd], [w.max_count for w in fd],
                     sum(w.usable for w in mids), sum(w.max_count for w in mids), costs.food(ds, req))


@dataclass
class Selection:
    hotel: Hotel
    out: int                  # index into Candidate.outs
    ret: int
    chosen: list              # [Attraction], file order
    objective: float
    est_cost: int
    est_value: float


def est_travel(ds: Dataset, cfg: Config, city: str, hotel: Hotel, a: Attraction) -> int:
    return round_half_up(cfg.chain_factor * 2 * ds.travel(city, hotel.hotel_id, a.attraction_id)[1])


def solve(ds: Dataset, cfg: Config, cand: Candidate, hotel: Hotel, mode: str = "max_value",
          budget: int | None = None, vstar: float | None = None, cuts: frozenset = frozenset(),
          fix: tuple | None = None, min_activities: int = 0) -> Selection | None:
    req = cand.req
    city = req.destination
    m = cp_model.CpModel()
    o = [m.NewBoolVar(f"o{j}") for j in range(len(cand.outs))]
    r = [m.NewBoolVar(f"r{j}") for j in range(len(cand.rets))]
    m.AddExactlyOne(o)
    m.AddExactlyOne(r)
    if fix is not None:
        m.Add(o[fix[0]] == 1)
        m.Add(r[fix[1]] == 1)
    attrs = [a for a in cand.attrs if a.attraction_id not in cuts]
    x = {a.attraction_id: m.NewBoolVar(a.attraction_id) for a in attrs}
    for lid in req.fixed_ids():
        if lid not in x:
            return None
        m.Add(x[lid] == 1)

    travel = {a.attraction_id: est_travel(ds, cfg, city, hotel, a) for a in attrs}
    local = {a.attraction_id: costs.est_local(ds, cfg, req, ds.travel(city, hotel.hotel_id, a.attraction_id)[0])
             for a in attrs}
    entry = {a.attraction_id: costs.entry(req, a.fee) for a in attrs}

    fixed_cost = costs.stay(req, hotel) + cand.food
    cost = (fixed_cost + sum(c * v for c, v in zip(cand.out_cost, o)) + sum(c * v for c, v in zip(cand.ret_cost, r))
            + sum((entry[k] + local[k]) * x[k] for k in x))

    # time and count capacity depend linearly on the chosen options (§7.3)
    m.Add(sum((a.visit + travel[a.attraction_id]) * x[a.attraction_id] for a in attrs)
          <= cand.u_mid + sum(u * v for u, v in zip(cand.u1, o)) + sum(u * v for u, v in zip(cand.ud, r)))
    limit = cand.c_mid + sum(c * v for c, v in zip(cand.c1, o)) + sum(c * v for c, v in zip(cand.cd, r))
    m.Add(sum(x.values()) <= limit)
    if min_activities:
        m.Add(sum(x.values()) >= min_activities)

    # variety: per primary tag ≤ max(variety_min, ⌈share × limit⌉)
    share = Fraction(str(cfg.variety_share)).limit_denominator(100)
    lim = m.NewIntVar(0, 1000, "limit")
    m.Add(lim == limit)
    ceil_part = m.NewIntVar(0, 1000, "ceil")
    m.AddDivisionEquality(ceil_part, share.numerator * lim + share.denominator - 1, share.denominator)
    cap = m.NewIntVar(0, 1000, "cap")
    m.AddMaxEquality(cap, [ceil_part, cfg.variety_min])
    for tag in sorted({a.tags[0] for a in attrs}):
        m.Add(sum(x[a.attraction_id] for a in attrs if a.tags[0] == tag) <= cap)

    vc = cfg.value
    mu = vc["mu_travel_per_min"]
    jv_o = [vc["kappa_t"] * op.comfort / 2 + vc["beta_pref_mode"] * op.preferred for op in cand.outs]
    jv_r = [vc["kappa_t"] * op.comfort / 2 + vc["beta_pref_mode"] * op.preferred for op in cand.rets]
    av = {k: cand.v[k] - mu * travel[k] for k in x}
    const_v = value.hotel_term(hotel.tier, cfg)
    v_scaled = (sum(round(SCALE * c) * v for c, v in zip(jv_o, o)) + sum(round(SCALE * c) * v for c, v in zip(jv_r, r))
                + sum(round(SCALE * av[k]) * x[k] for k in x) + round(SCALE * const_v))

    if budget is not None:
        m.Add(cost <= budget)
    if mode == "max_value":
        m.Maximize(v_scaled - cost)
    elif mode == "balanced":
        m.Maximize(budget * v_scaled - round(SCALE * cfg.variants["lambda"] * vstar) * cost)
    elif mode == "min_cost":
        if vstar is not None:
            m.Add(v_scaled >= round(SCALE * cfg.variants["rho"] * vstar))
        m.Minimize(cost)
    else:
        raise ValueError(mode)

    s = cp_model.CpSolver()
    p = cfg.cpsat
    s.parameters.num_workers = p["workers"]
    s.parameters.random_seed = p["seed"]
    s.parameters.max_time_in_seconds = p["time_limit_s"]
    status = s.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    oj = next(j for j, v in enumerate(o) if s.Value(v))
    rj = next(j for j, v in enumerate(r) if s.Value(v))
    chosen = [a for a in attrs if s.Value(x[a.attraction_id])]
    return Selection(hotel, oj, rj, chosen, s.ObjectiveValue(), int(s.Value(cost)), s.Value(v_scaled) / SCALE)


def best(ds: Dataset, cfg: Config, cand: Candidate, hotels: list, mode: str, **kw) -> Selection | None:
    """Solve one model per hotel; keep the best objective (ties: first hotel in file order)."""
    out = None
    for h in hotels:
        sel = solve(ds, cfg, cand, h, mode, **kw)
        if sel is None:
            continue
        better = (sel.objective < out.objective) if (out and mode == "min_cost") else (out is None or sel.objective > out.objective)
        if out is None or better:
            out = sel
    return out
