# 001 — City Data

Status: **Draft for review** · Created 2026-10-22
Traces to: FR-060, FR-061, FR-062, NFR-010 · Constitution Article III

---

## 1. Goal

Produce a curated, validated dataset for the 15 supported cities. It must hold everything the engine needs to price and schedule a trip: how to get between cities, what each journey costs, what to do in each city, where to stay, what food and local travel cost, and how long it takes to move between places inside a city.

The dataset lives as version-controlled CSV/JSON files in `data/curated/` and is loaded into Neon Postgres by a script. The files are the source of truth; the database is a loaded copy.

## 2. Scope

**In scope:** cities and access hubs, intercity pairs, fare rates, attractions, hotels, food allowances, local transport rates, intra-city travel-time matrices, a validation script and a loader script.

**Out of scope:** live prices, seasonal prices, metro and city-bus networks, restaurants as separate entities (food is an allowance), user-generated data.

## 3. Conventions

- **Money:** whole Indian rupees (integer).
- **Distance:** kilometres (decimal, 1 place). **Durations:** minutes (integer).
- **Times:** `HH:MM`, 24-hour, IST.
- **Weekdays:** integers 0–6, with 0 = Monday.
- **Coordinates:** WGS84 decimal degrees, 5 places.
- **IDs:** city codes from spec 000 (`JAI`, `AGR`, …). Other IDs are `<CITY>-<TYPE>-<NN>`, for example `JAI-A-07` (attraction) and `JAI-H-03` (hotel).
- **Provenance:** every curated row has `source` (URL or short citation) and `checked_on` (date).
- **Dataset version:** `data/curated/VERSION` holds the version (for example `1.0`) and the compilation month (for example `2026-11`). This is the month shown to users (FR-062).

## 4. Interest tags

Exactly these nine values are allowed, matching FR-005:

`nature`, `adventure`, `food`, `history`, `culture`, `spiritual`, `shopping`, `relaxation`, `nightlife`

## 5. Entities

### 5.1 `cities.csv` — 15 rows

| Field | Type | Rule |
|---|---|---|
| city_id | text | One of the 15 codes |
| name | text | |
| lat, lon | decimal | City centre |
| traffic_factor | decimal | Multiplier on free-flow drive times, 1.0–2.0. Suggested: 1.4 for DEL, BOM, BLR, CCU, HYD, MAA; 1.2 for JAI, AGR, VNS, GOA, PDY; 1.1 for the rest |
| food_multiplier | decimal | Multiplier on base food allowance, 0.8–1.5 |
| source, checked_on | | |

### 5.2 `hubs.csv` — access points per city

One row per city per mode. Some cities have no airport or railway station of their own, so the hub can be in a nearby town.

| Field | Type | Rule |
|---|---|---|
| city_id | text | |
| mode | enum | `train`, `bus`, `flight` |
| hub_name | text | For example "Hosapete Jn", "Kochi Intl Airport" |
| hub_code | text | Station or IATA code where one exists |
| lat, lon | decimal | |
| access_km | decimal | Road distance from hub to city centre |
| access_minutes | int | Drive time from hub to city centre |
| access_cost_per_vehicle | int | Typical cab or auto fare, hub to centre |
| source, checked_on | | |

Hubs that are expected to be outside the city and **must be verified** during collection:

| City | Train hub | Flight hub |
|---|---|---|
| Hampi | Hosapete | Nearest airport with regular flights (check Jindal Vijaynagar and Hubballi) |
| Munnar | Aluva or Ernakulam | Kochi |
| Rishikesh | Rishikesh or Haridwar | Dehradun (Jolly Grant) |
| Darjeeling | New Jalpaiguri | Bagdogra |
| Pondicherry | Puducherry | Chennai, if Puducherry has no regular flights |

A city with no usable hub for a mode has no row for that mode, and that mode is unavailable to and from it.

### 5.3 `city_pairs.csv` — 105 unordered pairs

Each row covers both directions; the loader expands it to 210 directed pairs.

| Field | Type | Rule |
|---|---|---|
| city_a, city_b | text | city_a < city_b alphabetically |
| road_km | decimal | Between the bus hubs, from OpenRouteService |
| rail_km | decimal | From a published train route if collected; otherwise equal to road_km and `rail_km_approx = true` |
| air_km | decimal | Great-circle distance between flight hubs |
| train_available | bool | Both cities have a train hub, and a direct or one-change train exists |
| bus_available | bool | Both cities have a bus hub, and road_km ≤ 1,000 |
| flight_available | bool | Both cities have a flight hub, a direct or one-stop route exists, and air_km ≥ 300 |
| train_minutes | int | Published typical time if known; otherwise rail_km ÷ 55 km/h × 60 + 60 |
| bus_minutes | int | Published typical time if known; otherwise road_km ÷ 45 km/h × 60 + 30 |
| flight_minutes | int | Gate to gate: published time if known, otherwise air_km ÷ 600 km/h × 60 + 30. Add 120 for one-stop routes |
| rail_km_approx | bool | |
| source, checked_on | | |

**Rule:** the engine adds 90 minutes airport overhead to every flight, and the hub access time (5.2) to every journey at both ends. These are not stored in `*_minutes`.

### 5.4 `fare_rates.csv` — one row per mode and class

| mode | class | Meaning |
|---|---|---|
| train | SL | Sleeper |
| train | 3A | AC 3-tier |
| train | 2A | AC 2-tier |
| bus | NAC | Non-AC seater |
| bus | ACS | AC sleeper |
| flight | Y | Economy |

| Field | Type | Rule |
|---|---|---|
| mode, class | enum | As above |
| base_fare | int | Fixed charge per person per journey (reservation, fees) |
| per_km | decimal | Per person per km, on rail_km / road_km / air_km |
| min_fare | int | Floor per person |
| comfort_value | decimal | 0–1, used by the engine's value function. Defaults: SL 0.2, 3A 0.6, 2A 0.8, NAC 0.1, ACS 0.5, Y 0.9 |
| source, checked_on | | Published fare chart or a sample of real fares, with the method recorded |

**Fare formula** (per person, one way) = max(min_fare, base_fare + per_km × distance).

**Sanity bounds** for validation. These only catch typos and are not price claims:

| class | per_km |
|---|---|
| SL | 0.3–1.0 |
| 3A | 0.9–2.2 |
| 2A | 1.4–3.2 |
| NAC | 0.8–2.0 |
| ACS | 1.5–3.5 |
| Y | 2.0–9.0, with base_fare 1,000–4,000 |

### 5.5 `attractions.csv` — 25 to 40 per city

| Field | Type | Rule |
|---|---|---|
| attraction_id | text | `<CITY>-A-<NN>` |
| city_id | text | |
| name | text | |
| lat, lon | decimal | Within 60 km of the city centre |
| visit_minutes | int | Typical visit, 20–480 |
| open_time, close_time | HH:MM | Opening and closing time; a visit must finish by close_time. open < close, and close − open ≥ visit_minutes. Use 00:00–23:59 for always open |
| closed_weekdays | list of int | For example `[0]` for closed Mondays; empty if open daily |
| entry_fee | int | Indian adult, per person; 0 allowed |
| tags | list | 1–3 interest tags from section 4. The first is the primary tag |
| rating | decimal | 1.0–5.0, from a public rating source; record which |
| outdoor | bool | |
| crowd_level | enum | `low`, `medium`, `high` |
| fixed_slot | bool | True for events at a set time, such as Ganga Aarti. Then open_time/close_time is the event window and visit_minutes fits inside it |
| source, checked_on | | Opening hours and fee source; may differ from seed source |

**Coverage rules:**

- Each city has at least 25 attractions.
- Every interest tag that fits the city's character (spec 000, section 4) appears on at least 3 of its attractions.
- At least 5 attractions per city have `entry_fee = 0`.

### 5.6 `hotels.csv` — 3 tiers × 3–4 hotels per city

| Field | Type | Rule |
|---|---|---|
| hotel_id | text | `<CITY>-H-<NN>` |
| city_id | text | |
| name | text | Real property name |
| tier | enum | `budget`, `mid`, `premium` |
| lat, lon | decimal | Within 25 km of the city centre |
| price_per_room_night | int | Typical double-occupancy price |
| source, checked_on | | |

**Tier price bands:** these are sanity bounds, per room per night.

| Tier | Range | Typical |
|---|---|---|
| budget | ₹600–2,500 | hostels, guesthouses, budget hotels |
| mid | ₹2,000–6,000 | |
| premium | ₹5,000–20,000 | |

Hotels within a city should spread across at least two areas so location matters.

### 5.7 `food.csv`

Three rows, one per comfort level, giving `base_per_person_per_day`. City cost = base × the city's `food_multiplier`.

### 5.8 `local_transport.csv` — 2 rows per city

| Field | Type | Rule |
|---|---|---|
| city_id | text | |
| mode | enum | `auto`, `cab` |
| base_fare | int | Per vehicle per ride |
| per_km | decimal | Per vehicle |
| capacity | int | People per vehicle: auto 3, cab 4 |
| source, checked_on | | |

Ride cost = (base_fare + per_km × km) × ⌈people ÷ capacity⌉.

### 5.9 `matrices/<CITY>.json` — intra-city travel

A distance and time matrix covering every hotel, every attraction and the city's hubs, from the OpenRouteService `driving-car` profile.

```json
{
  "city_id": "JAI",
  "profile": "driving-car",
  "computed_on": "2026-11-02",
  "nodes": ["JAI-H-01", "JAI-A-01", "JAI-HUB-train"],
  "km": [[0.0, 4.2, 6.1], [4.2, 0.0, 3.3], [6.1, 3.3, 0.0]],
  "minutes_free_flow": [[0, 11, 15], [11, 0, 9], [15, 9, 0]]
}
```

The engine applies `traffic_factor` at runtime. Raw API responses are cached in `data/raw/ors/` so the matrix can be rebuilt without new API calls.

## 6. Collection workflow

1. **Seed attractions:** a script queries OpenTripMap (and OpenStreetMap through Overpass where useful) for each city and writes candidates to `data/raw/seed_<CITY>.json`.
2. **Curate:** choose 25–40 attractions per city. Fill visit time, hours, closed days, fee, tags, rating, crowd level and sources by hand, checking official sites where they exist.
3. **Hubs, pairs and fares:** fill `hubs.csv` and `fare_rates.csv` by hand. A script computes `road_km` and `air_km` and the formula fallbacks for `city_pairs.csv`, then known published times are entered as overrides.
4. **Hotels, food and local transport:** fill by hand from public listings, recording sources.
5. **Matrices:** a script calls OpenRouteService once per city and writes `matrices/<CITY>.json`.
6. **Validate:** `python -m data.validate` must report 0 errors.
7. **Load:** `python -m data.load` truncates and reloads the Neon tables inside one transaction, and records the dataset version.

## 7. Requirements

- **DATA-FR-01** The dataset contains exactly 15 cities with the fields in 5.1. (FR-060)
- **DATA-FR-02** Every city has at least one hub, and every hub has access distance, time and cost. (FR-060)
- **DATA-FR-03** `city_pairs.csv` has exactly 105 unordered pairs. Every pair has at least one available mode. Every available mode has a positive duration. (FR-060)
- **DATA-FR-04** `fare_rates.csv` has the 6 mode-class rows, each within its sanity bounds. (FR-060)
- **DATA-FR-05** Every city meets the attraction coverage rules in 5.5. (FR-060)
- **DATA-FR-06** Every city has 3–4 hotels in each tier, within the tier's price band. (FR-060)
- **DATA-FR-07** Every city has a complete matrix whose nodes are exactly its hotels, attractions and hubs. All off-diagonal values are positive, and the diagonal is 0. (FR-060)
- **DATA-FR-08** Every curated row has a non-empty `source` and a valid `checked_on` date. (FR-061)
- **DATA-FR-09** `data/curated/VERSION` exists, and the loader writes its version and compilation month to the database. (FR-062)
- **DATA-FR-10** The validator checks every rule in sections 3–5 and 7. It prints each error with file, row and field, and exits non-zero if any error is found. (NFR-010)
- **DATA-FR-11** The loader is all-or-nothing: if any insert fails, the database keeps its previous data.
- **DATA-FR-12** Every approximation used (`rail_km_approx`, formula-derived durations) is flagged in the row so the evaluation can report how much of the data is approximate. (Constitution III.3)

## 8. Acceptance tests

| ID | Test | Pass when |
|---|---|---|
| DATA-AT-01 | Run `python -m data.validate` on the shipped dataset | Exit code 0, "0 errors" |
| DATA-AT-02 | Validator self-test: run it on fixtures that each break one rule (missing source, bad tag, open ≥ close, unknown city, price outside band, missing matrix node, pair with no mode) | Each fixture produces exactly the expected error, and the run exits non-zero |
| DATA-AT-03 | Run `python -m data.load` against Neon | Row counts in the database equal the CSV counts. The version table shows the VERSION contents |
| DATA-AT-04 | Make the loader fail partway (bad row injected in a test copy) | Previous database contents unchanged |
| DATA-AT-05 | Spot check: pick 10 random attractions and 5 random hotels and re-check them against their source | At least 9 of 10 and 5 of 5 match. Record results in `data/spot_check.md` |
| DATA-AT-06 | Count report: `python -m data.report` | Prints per-city counts, and the share of pairs with approximate rail distance and with formula durations |

## 9. Risks

- **Time:** curating ~500 attractions is the largest manual task in the project. Mitigation: start on Day 2, curate the 5 cities used most in test trips first, and use the seed script to pre-fill names, coordinates and tags.
- **Opening hours accuracy:** OpenStreetMap hours are incomplete. Mitigation: prefer official sites; when hours can't be confirmed, use the site's commonly stated hours and record that in `source`.
- **OpenRouteService limits:** the free tier caps requests per day and matrix size. Mitigation: one matrix call per city (about 55 nodes), with cached responses.

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-10-22 | Initial draft | Phase 0 |
