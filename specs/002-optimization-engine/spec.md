# 002 — Optimization Engine (single plan)

Status: **Draft for review** · Created 2026-10-22
Traces to: FR-010–FR-015, NFR-008, NFR-009 · Constitution Articles II and IX
Depends on: 001 City data

---

## 1. Goal

Given a trip request, produce **one** feasible plan with the highest trip value, or a clear "no plan fits" answer with the minimum budget needed. The plan is checked by an independent validator before it is returned.

Variants (Saver / Balanced / Experience) and trade-offs are built on top of this engine in spec 003.

## 2. Scope

**In scope:**

- the time model (trip days, first and last day windows, overnight travel),
- the cost model,
- the trip value function,
- stage 1 (selection, CP-SAT) and stage 2 (scheduling, OR-Tools routing) with the feedback loop between them,
- the infeasibility answer,
- the plan validator,
- the configuration file,
- a command-line harness,
- the 30 test trips.

**Out of scope:** variants and trade-offs (003), HTTP endpoints (005), LLM features (007), date-range checks against today (005).

## 3. Input — `TripRequest`

```json
{
  "origin": "BLR",
  "destination": "JAI",
  "start_date": "2026-12-18",
  "end_date": "2026-12-21",
  "people": 2,
  "budget_total": 40000,
  "prefs": {
    "daily_hours_out": 9,
    "interests": {"nature": 1, "adventure": 0, "food": 4, "history": 5, "culture": 3,
                  "spiritual": 0, "shopping": 2, "relaxation": 1, "nightlife": 0},
    "pace": "balanced",
    "comfort": "mid",
    "modes": {"train": "neutral", "bus": "avoid", "flight": "preferred"},
    "avoid_crowds": false
  },
  "locks": [],
  "excludes": []
}
```

- **Dates:** `start_date` is the first day at the destination (arrival day). `end_date` is the last day at the destination (departure day). D = end − start + 1, from 2 to 7.
- **Budget:** `budget_total` is always the total. Per-person conversion happens in the API.
- **Locks and excludes:** lists of attraction IDs, which must belong to the destination city.

## 4. Time model

All times are minutes after midnight, IST.

### 4.1 Day windows

- **Daily window:** each day d = 1…D has a nominal window [S, S + H], where S = `day_start` (config, default 09:00) and H = `daily_hours_out` × 60. The window end is capped at `day_end_cap` (default 23:00).
- **Lunch:** a day whose window is at least 6 hours gets a 60-minute lunch break that must start between 12:30 and 14:30. It is modelled as a break in the routing time dimension.
- **Pace:** pace sets the activity limit per day and the share of the window that may be used.

| Pace | Max activities per day | Window fill |
|---|---|---|
| relaxed | 3 | 0.75 |
| balanced | 4 | 0.90 |
| packed | 6 | 1.00 |

### 4.2 Journey time

For a transport option (mode m, class k), the door-to-door journey time is:

J = origin hub access + mode minutes + (90 if flight) + destination hub access

Hub access comes from `hubs.csv`; mode minutes come from `city_pairs.csv`.

**Options removed before solving:**

- modes the user avoids,
- modes not available for the pair,
- train or bus journeys with mode minutes > 1,200 (20 hours). These are too long for a 2–7 day trip.

If no option remains in either direction, the answer is `no_route` (section 8).

### 4.3 First and last day

| Journey type | Rule |
|---|---|
| **Daytime** (flights; train/bus with mode minutes < 480) | **Outbound:** surface journeys leave the origin hub at 06:00 on day 1; flights depart at 07:00. Arrival at the destination centre = departure + mode minutes + destination access. Day 1 window starts at max(S, that arrival + 30). **Return:** must reach the origin hub by 23:00 on day D, so the latest departure from the destination centre = 23:00 − (mode minutes + destination access + 90 if flight). Day D window ends at min(window end, latest departure − 30). |
| **Overnight** (train/bus with 480 ≤ mode minutes ≤ 1,200) | **Outbound:** arrives at the destination hub at 07:00 on day 1. Day 1 window starts at max(S, 07:00 + destination access + 60). **Return:** leaves the destination hub at 21:00 on day D. Day D window ends at min(window end, 21:00 − destination access − 30). |

- A day whose window ends up shorter than 60 minutes has no activities.
- **Approximation:** the hotel stands in for the city centre when applying these rules (Constitution III.3).

### 4.4 Usable time per day

U_d = (window length_d − lunch_d) × window fill

## 5. Cost model

All amounts are integer rupees; P = people.

| Item | Formula |
|---|---|
| Outbound | P × fare(m, k, distance) + destination-side access cost × ⌈P ÷ capacity⌉ |
| Return | Same as outbound, in the other direction |
| Stay | (D − 1) nights × ⌈P ÷ 2⌉ rooms × hotel price per room per night |
| Food | P × D × food base(comfort) × city food multiplier |
| Entry fees | P × Σ entry fee of the chosen activities |
| Local travel | Σ over route legs of ride cost(km), using auto for `budget` comfort and cab for `mid`/`premium` (spec 001, 5.8) |
| **Total** | Sum of the above |
| **Contingency** | Budget − ⌊0.9 × budget⌋ (shown separately) |

- The fare formula is max(min_fare, base_fare + per_km × distance), using rail_km, road_km or air_km for the mode.
- Origin-side hub access is assumed to be paid by the traveller outside the trip budget, and is excluded. (Assumption, listed in section 13.)
- **Hard budget rule:** Total ≤ ⌊0.9 × budget_total⌋.

## 6. Trip value

### 6.1 Activity value

For activity a with tags t₁ (primary), t₂, t₃ and user weights w (0–5):

- match(a) = max over its tags of (w_tag ÷ 5) × (1.0 if the tag is primary, else 0.6)
- crowd(a) = 0.7 if `avoid_crowds` and crowd_level = high; 0.85 if `avoid_crowds` and crowd_level = medium; otherwise 1.0
- **v(a) = 100 × (rating ÷ 5) × (0.2 + 0.8 × match(a)) × crowd(a)**

An activity with match 0 keeps 20% of its rating value. This lets highly rated places fill spare time without outranking matched ones.

### 6.2 Plan value

V = Σ v(a) over chosen activities
  + κ_t × (comfort_value(outbound) + comfort_value(return)) ÷ 2
  + β × (number of journeys using a preferred mode)
  − μ × (total minutes of local travel)

**Defaults:** κ_t = 15, β = 5, μ = 0.05 per minute. All of these are in the config file (NFR-009).

## 7. Algorithm

### 7.1 Pre-filter

Drop an attraction if any of the following is true:

- it is in `excludes`,
- it is closed on every trip day,
- its open interval cannot contain its visit inside any day's window.

A locked attraction that would be dropped makes the request infeasible, with the reason `lock_impossible` naming the attraction.

### 7.2 Candidate hotels

All hotels of the user's comfort tier in the destination city (3–4 hotels).

### 7.3 Stage 1 — selection (CP-SAT, one model per candidate hotel)

**Variables:**

- o_j ∈ {0,1} for each outbound option, with Σ o_j = 1,
- r_j ∈ {0,1} for each return option, with Σ r_j = 1,
- x_a ∈ {0,1} for each remaining attraction.

**Estimates used only in stage 1** (stage 2 replaces them with exact routed values):

- est_travel(a) = 0.6 × 2 × time(hotel, a) × traffic_factor
- est_local_cost(a) = ride_cost(0.6 × 2 × km(hotel, a))

The 0.6 factor approximates the saving from chaining stops instead of returning to the hotel between them.

**Constraints:**

1. **Budget:** total cost with estimated local travel ≤ ⌊0.9 × budget⌋.
2. **Time:** Σ x_a × (visit(a) + est_travel(a)) ≤ Σ_d U_d. Here U_1 and U_D depend linearly on the chosen o and r through section 4.3: precompute U_1 for each outbound option and U_D for each return option.
3. **Count:** Σ x_a ≤ Σ over days with activities of (max activities per day). The day-1 and day-D terms depend on o and r.
4. **Variety:** for each primary tag g, Σ x_a over attractions with primary tag g ≤ max(2, ⌈0.4 × total activity limit⌉).
5. **Locks:** x_a = 1 for every locked attraction.

**Objective:** maximize 1000 × V − cost. The cost term breaks ties toward the cheaper plan.

Pick the hotel whose model gives the highest objective.

### 7.4 Stage 2 — scheduling (OR-Tools routing)

**Model:**

- **Vehicles:** one per day with activities; vehicle d has the day-d window.
- **Depot:** the hotel. Every day starts and ends at the hotel (section 4.3 approximation).
- **Nodes:** the activities chosen in stage 1.
- **Time dimension:** transit(i → j) = visit(i) + time(i, j) × traffic_factor. Vehicle d's start ≥ its window start and its end ≤ its window end. The route span ≤ U_d plus lunch.
- **Node time windows:** a visit starts within [open, close − visit].
- **Allowed vehicles:** an activity cannot be assigned to a day whose weekday is in its `closed_weekdays`.
- **Count dimension:** at most the pace's activities per day.
- **Lunch:** a 60-minute break on each day with a window of at least 6 hours.
- **Dropping:** every activity is optional, with drop penalty = 1000 × v(a). Locked activities cannot be dropped.

**Search:** first solution `PATH_CHEAPEST_ARC`, then `GUIDED_LOCAL_SEARCH`, with time limit `routing_time_limit_s` (default 1.0).

### 7.5 Feedback loop

If stage 2 drops a set S of activities:

1. Add the cut x_a = 0 for every a in S to stage 1. Keep the hotel and transport fixed.
2. Re-solve stage 1, then re-route.
3. Repeat until nothing is dropped, or `max_feedback_iters` (default 3) is reached.

The final plan is the last routed solution, which is feasible by construction.

### 7.6 Exact costing and budget repair

Compute the exact local travel cost from the routed legs. If the exact total exceeds ⌊0.9 × budget⌋:

1. Remove the activity with the lowest v(a) ÷ (entry cost + its legs' cost).
2. Re-route.
3. Repeat until the plan fits the budget.

Locked activities are never removed. If they alone break the budget, the answer is infeasible with `lock_over_budget`.

### 7.7 Validation

Run the validator (section 9) on the final plan. A validator failure is a bug: the engine returns error `internal_validation_failed` with the list of failed checks, and never returns the plan.

## 8. Output

### 8.1 Success — `Plan`

```json
{
  "status": "ok",
  "dataset_version": "1.0 (2026-11)",
  "request_hash": "sha256:…",
  "value": 412.6,
  "transport": {
    "outbound": {"mode": "flight", "class": "Y", "depart": "07:00", "arrive_centre": "10:05",
                 "minutes": 305, "overnight": false, "cost": 9500},
    "return":   {"mode": "flight", "class": "Y", "leave_centre": "15:40", "arrive_origin": "22:30",
                 "minutes": 410, "overnight": false, "cost": 8800}
  },
  "hotel": {"hotel_id": "JAI-H-05", "name": "…", "tier": "mid", "nights": 3, "rooms": 1,
            "price_per_room_night": 3200, "cost": 9600},
  "days": [
    {"day": 1, "date": "2026-12-18", "weekday": 4,
     "window": ["10:35", "18:00"], "lunch": ["13:10", "14:10"],
     "stops": [
       {"attraction_id": "JAI-A-03", "name": "…", "arrive": "11:00", "start": "11:00",
        "end": "12:30", "entry_cost": 400,
        "leg_from_prev": {"from": "JAI-H-05", "minutes": 25, "km": 7.4, "mode": "cab", "cost": 210}}
     ],
     "return_leg": {"to": "JAI-H-05", "minutes": 18, "km": 5.1, "mode": "cab", "cost": 160}}
  ],
  "budget": {"outbound": 9500, "return": 8800, "stay": 9600, "food": 3200, "entry_fees": 1700,
             "local_travel": 1950, "total": 34750, "usable_budget": 36000, "contingency": 4000,
             "budget_total": 40000, "estimate_label": "Estimated prices, compiled Nov 2026"},
  "near_misses": [{"attraction_id": "JAI-A-11", "name": "…", "reason": "time"}],
  "solver": {"hotel_candidates": 4, "feedback_iters": 1, "repairs": 0, "solve_ms": 1830}
}
```

> The numbers above illustrate the format only; they are not real prices.

- `near_misses` here is a simple list: up to five unchosen activities with the highest v(a), each with a reason from {`budget`, `time`, `closed`}. Spec 003 refines how the reasons are computed.

### 8.2 Not feasible

```json
{"status": "infeasible", "reason": "budget", "min_budget_total": 52500,
 "message": "No plan fits ₹40,000 for 2 people over 4 days. The cheapest workable plan needs about ₹52,500."}
```

| reason | Meaning |
|---|---|
| `budget` | No plan with at least one activity fits the budget |
| `no_route` | No usable transport option in one or both directions |
| `lock_impossible` | A locked activity cannot be scheduled on any trip day |
| `lock_over_budget` | Locked activities alone exceed the budget |

**Minimum budget:** solve stage 1 with the objective "minimize cost", subject to at least one activity and all locks. Then min_budget_total = ⌈(min cost ÷ 0.9) ÷ 500⌉ × 500.

## 9. Validator

`validate(plan, request, dataset) → list of failures` (empty means valid). It recomputes everything from the dataset and does not trust any field in the plan.

| Check | Rule |
|---|---|
| V-01 | Origin, destination, dates and people match the request |
| V-02 | Transport modes are available for the pair, not avoided, and within the 1,200-minute limit |
| V-03 | Every cost line equals its recomputed value (section 5), and the lines sum to the total |
| V-04 | Total ≤ ⌊0.9 × budget_total⌋ |
| V-05 | No attraction appears twice; all belong to the destination city |
| V-06 | No visit falls on a closed weekday |
| V-07 | Every visit starts at or after open and ends by close |
| V-08 | Leg times equal matrix time × traffic factor (±1 min), and stop times are consistent: arrive = previous end + leg; start ≥ arrive; end = start + visit |
| V-09 | Each day's first departure and last return lie within that day's window (section 4.3) |
| V-10 | Each day's span (hotel departure to hotel return, minus lunch) ≤ U_d, and its activity count ≤ the pace limit |
| V-11 | Lunch is 60 minutes, starts between 12:30 and 14:30 and does not overlap a visit, on days whose window is at least 6 hours |
| V-12 | Every lock is present; no exclude is present |
| V-13 | Hotel is in the destination city and in the requested tier; nights = D − 1; rooms = ⌈P ÷ 2⌉ |

The validator is a separate module with no imports from the solver code, so it can also check the baseline planners in spec 008.

## 10. Configuration — `backend/tripwise/config.yaml`

| Key | Default |
|---|---|
| day_start | "09:00" |
| day_end_cap | "23:00" |
| usable_budget_share | 0.90 |
| pace | {relaxed: {max: 3, fill: 0.75}, balanced: {max: 4, fill: 0.90}, packed: {max: 6, fill: 1.00}} |
| lunch | {min_window_h: 6, minutes: 60, earliest: "12:30", latest: "14:30"} |
| overnight_min_minutes | 480 |
| max_surface_minutes | 1200 |
| flight_overhead_minutes | 90 |
| chain_factor | 0.6 |
| value | {kappa_t: 15, beta_pref_mode: 5, mu_travel_per_min: 0.05, secondary_tag: 0.6, base_share: 0.2, crowd: {high: 0.7, medium: 0.85}} |
| variety_share | 0.4 |
| cpsat | {time_limit_s: 0.4, workers: 1, seed: 42} |
| routing_time_limit_s | 1.0 |
| max_feedback_iters | 3 |
| min_budget_round | 500 |

## 11. Requirements

- **ENG-FR-01** The engine implements the time model in section 4 exactly, including overnight rules and lunch. (FR-011, FR-014)
- **ENG-FR-02** The engine implements the cost model in section 5. Budget lines sum exactly to the total, and the contingency is reported. (FR-010, FR-013, FR-015)
- **ENG-FR-03** The engine implements the value function in section 6 with weights from config. (FR-010, NFR-009)
- **ENG-FR-04** Stage 1, stage 2, the feedback loop and budget repair work as in section 7. (FR-010, FR-011)
- **ENG-FR-05** For a feasible request, the output matches the `Plan` schema in 8.1, and every itinerary entry has times, fee, leg mode, leg time and leg cost. (FR-010, FR-014)
- **ENG-FR-06** For an infeasible request, the output matches 8.2. For `budget`, it gives the minimum budget computed as in 8.2. (FR-012)
- **ENG-FR-07** Every returned plan passes the validator. Otherwise the engine returns `internal_validation_failed`. (FR-011, Constitution II.1)
- **ENG-FR-08** The validator implements checks V-01 to V-13 and shares no code with the solver. (FR-011)
- **ENG-FR-09** All tunables are read from `config.yaml`. (NFR-009)
- **ENG-FR-10** The same request and dataset version produce identical output, apart from `solve_ms`. (NFR-008)
- **ENG-FR-11** A command-line harness runs `python -m tripwise.cli plan <request.json>` and prints a readable plan, or the infeasible message. `python -m tripwise.cli batch eval/test_trips.json` runs all test trips and prints a summary table.
- **ENG-FR-12** `eval/test_trips.json` holds 30 test trips that meet the coverage rules in section 12.

## 12. Test trips — coverage rules

The 30 trips in `eval/test_trips.json` must together include:

- at least 10 different destinations and at least 15 different city pairs,
- every trip length from 2 to 7 days,
- group sizes 1, 2, 3, 4 and 6,
- each pace and each comfort tier at least 5 times,
- at least 5 trips that include a Monday (to exercise closures),
- at least 3 overnight-eligible pairs, and 3 pairs where only flights are practical,
- at least 3 trips with a mode avoided, and 3 with `avoid_crowds` on,
- budgets of three kinds: at least 8 tight (within 15% of the minimum budget), 8 medium and 8 generous,
- at least 3 trips that are deliberately infeasible (budget below the minimum), and 1 with a lock that cannot be scheduled,
- at least 3 trips with locks and 3 with excludes.

Each trip has an `id`, a short `note` explaining what it tests, and an `expect` field: `ok` or an infeasible reason.

## 13. Assumptions introduced by this spec

- **E-A1** Origin-side hub access cost is outside the trip budget, but its time counts.
- **E-A2** Daytime journeys leave at 06:00 (surface) or 07:00 (flights). Overnight journeys arrive at 07:00 and leave at 21:00.
- **E-A3** The hotel location stands in for the city centre for arrival and departure timing.
- **E-A4** Early hotel check-in is possible on day 1, and late checkout is not needed on day D, because the last night is D − 1.
- **E-A5** Local travel uses one mode per trip based on comfort tier (A-05).

## 14. Acceptance tests

| ID | Test | Pass when |
|---|---|---|
| ENG-AT-01 | `cli batch eval/test_trips.json` | Every trip returns its `expect` status. Every `ok` plan passes the validator |
| ENG-AT-02 | Unit tests for the time model: daytime and overnight trips in both directions, a day with < 60 min window, lunch on/off at the 6 h boundary | All pass |
| ENG-AT-03 | Unit tests for the cost model on hand-computed examples (1, 3 and 6 people; auto and cab) | Match to the rupee |
| ENG-AT-04 | Unit tests for v(a) on hand-computed examples, including crowd penalty and secondary tags | Match to 0.01 |
| ENG-AT-05 | Validator self-tests: one hand-made broken plan per check V-01–V-13 | Each is caught by exactly the intended check |
| ENG-AT-06 | Run every `ok` test trip twice | Identical output, apart from `solve_ms` |
| ENG-AT-07 | Infeasible trips: re-run each one with budget = its reported `min_budget_total` | Each now returns `ok` |
| ENG-AT-08 | Timing on the developer laptop for the 30 trips | Single-plan solve p95 ≤ 2.5 s. This leaves room for three variants within NFR-001's 5 s once 003 adds them |
| ENG-AT-09 | Change a value weight in config and re-run one trip | Output changes, and no code edit was needed |

## 15. Risks

- **Stage 1 estimates too optimistic:** if the 0.6 chain factor underestimates travel, stage 2 drops items often. Mitigation: log the drop rate in batch runs and tune `chain_factor` in config.
- **Routing time limit vs speed:** guided local search improves with time. Mitigation: measure value against time limit on the test trips and pick the knee point.
- **One-hotel-per-model loop:** 3–4 hotels × stage 1 is cheap, but variants in 003 may widen the candidate set. Mitigation: keep the stage 1 time limit low and reuse the model across hotels.

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-10-22 | Initial draft | Phase 0 |
