# Tripwise — Specification

The single source of truth for Tripwise (UMC301 Project 4), built with spec-driven development.
Last updated 2026-10-22.

## How this document works

- This is the **only** spec file. Each phase adds its content here; nothing lives in separate spec files.
- **Part A** (Constitution) and **Part B** (Product) are fixed once approved. They change only through a Changelog entry.
- **Part C** grows one feature at a time. Each feature has three subsections, written in this order:
  - **Spec:** what and why, with requirement IDs and acceptance tests.
  - **Plan:** how it will be built.
  - **Tasks:** an ordered checklist; Claude Code ticks these.
- **Part D** (Traceability) is updated as each feature's tasks and tests are done.
- **Section references:** inside a feature, "section 4.3" means that feature's own Spec section 4.3. References elsewhere name the part, e.g. "Part B §4" or "Feature 001 Spec §5.8".
- Every change gets a row in the **Changelog** at the end, and a commit named `spec(<section>): <change> — <reason>`.

## Contents

- Part A — Constitution
- Part B — Product
- Part C — Features
  - 001 City data: Spec, Plan, Tasks
  - 002 Optimization engine: Spec (Plan and Tasks to be added)
  - 003–009: added phase by phase
- Part D — Traceability
- Changelog

---

## Part A — Constitution

Version 1.1 · Ratified 2026-10-22. These are the project-wide rules. Every section of Part C and every line of code must follow them.

### Article I — The spec is the source of truth

1. No code is written for a feature until its Spec, Plan and Tasks subsections in Part C of this document are approved.
2. Code implements the spec. If code needs to behave differently from the spec, the spec is changed first, then the code.
3. A feature is **done** only when every acceptance test in its spec passes and the result is recorded in Part D (Traceability).

### Article II — The solver owns feasibility

1. Every plan shown to a user is produced by the optimization engine and has passed the independent plan validator.
2. The LLM never creates, edits or reorders a plan. It may only:
   - turn free text into structured preferences (a fixed JSON schema),
   - turn a chat message into one action from the fixed action set,
   - explain a plan using data the engine produced.
3. Every LLM output is schema-validated before use. Invalid output is rejected and never reaches the solver or the user as fact.
4. The app must still generate plans when the LLM is unavailable. Only explanations and chat are lost.

### Article III — Honest data

1. Every price shown is labelled as an estimate, with the month the estimate was compiled.
2. Every curated number (fare rate, entry fee, hotel price, opening hours) records its source and the date it was checked.
3. Approximations are documented where they are made (for example, rail distance approximated by road distance) and listed in the spec that introduces them.
4. Nothing is invented to fill a gap. Missing data is marked missing and fails validation until filled.

### Article IV — Testable requirements

1. Every requirement has an ID: `FR-xxx` / `NFR-xxx` in Part B, and feature-scoped IDs (for example `DATA-FR-01`, `ENG-FR-01`) in Part C.
2. Every feature requirement traces to at least one product requirement.
3. Every requirement has an acceptance criterion that a test or a recorded manual check can decide pass or fail. Words like "fast", "good" or "realistic" must come with a number or a procedure.

### Article V — Test before done

1. Each feature's acceptance tests are written from its spec before or alongside the implementation, never after the fact to match whatever the code does.
2. The engine and validator have automated tests. Pages and chat flows have at least a written manual test script with recorded results.
3. A failing acceptance test blocks the next feature in the build order.

### Article VI — Fixed stack

| Layer | Choice |
|---|---|
| Frontend | React (Vite), Leaflet with OpenStreetMap tiles, deployed on Vercel |
| Backend | Python 3.11+, FastAPI, Google OR-Tools (CP-SAT and routing), deployed on the Azure VM |
| Database | PostgreSQL on Neon |
| LLM | Groq API |
| Geo data | OpenStreetMap / OpenTripMap (attraction seeding), OpenRouteService (travel times) |

Adding a new external service or library with a large footprint requires a spec amendment that says why.

### Article VII — Scope discipline

1. Only the 15 cities in the product spec are supported.
2. Items in the product spec's **Out of scope** list are not built, even partially, unless the product spec is amended.
3. When in doubt, build the smaller version that satisfies the acceptance criteria.

### Article VIII — Security and privacy

1. Passwords are hashed with bcrypt. Plain-text passwords are never stored or logged.
2. A user can read and change only their own data. Every data endpoint checks ownership.
3. Secrets (API keys, database URL, JWT secret) live in environment variables, never in the repository. `.env.example` lists the names without values.
4. Only the data needed for the app is collected: email, password hash, preferences, trips and chat history.

### Article IX — Reproducibility

1. The same request on the same deployment and dataset version returns the same plans. Solver seeds and time limits are fixed in configuration.
2. Tunable weights and limits live in one configuration file, not scattered through code.
3. The evaluation can be re-run with one command and produces the same results table from the same inputs.

### Article X — Change control

1. Every spec change is committed with a message of the form `spec(<section>): <what changed> — <why>`, e.g. `spec(002): …` or `spec(B): …`.
2. Every change to this document adds a row to the **Changelog** at the end, with date, section, change and reason.
3. A change that affects another feature updates that feature's subsections in the same commit.

---

### Governance

- This constitution takes precedence over every other part of this document.
- Amendments are made by editing Part A, bumping the version (1.0 → 1.1 for clarifications, 2.0 for a changed rule), and adding a Changelog entry below.
- Before each feature is marked done, check its work against every Article.

---

## Part B — Product

Status: **Approved** 2026-10-22

### 1. Summary

Tripwise is a web app that plans a complete budget trip between two of 15 Indian cities. The user enters where and when they are going, how many people, the budget and their preferences. Tripwise returns two or three feasible plans. Each plan covers transport there and back, accommodation, local travel, a day-by-day itinerary, a budget breakdown and trade-offs. The user picks a plan and refines it through a chat assistant. Plans and history are saved to the user's account.

Tripwise has two layers:

- **Optimization engine:** chooses transport, accommodation and activities that respect the budget, trip duration, opening hours, travel times and daily time limits, while maximizing a defined trip value.
- **AI assistant (Groq LLM):** turns free-text preferences into structured weights, explains plans in plain language, and maps chat requests onto a fixed set of plan changes that the engine then carries out.

The guiding rule: the engine guarantees that every plan is feasible; the AI layer never edits a plan directly (Constitution, Article II).

### 2. Problem and motivation

Planning a budget trip means juggling fares, hotel prices, entry fees, opening hours, distances and personal interests at the same time. Spreadsheets don't handle the scheduling, and asking a general-purpose LLM produces plans that read well but often break the budget, visit places on days they are closed or pack days with impossible travel. Tripwise combines constrained optimization, which gives guarantees, with an LLM, which gives a natural interface.

### 3. Users

- **Primary:** students and young working people planning short domestic trips (2–7 days) alone or in small groups, often on a tight budget.
- **Secondary:** the course instructor and evaluators, who need to see clearly how the system works and why its plans are trustworthy.

### 4. Supported cities

| Code | City | Character |
|---|---|---|
| JAI | Jaipur | Heritage |
| AGR | Agra | Heritage |
| HMP | Hampi | Heritage |
| MUN | Munnar | Nature |
| RSH | Rishikesh | Nature, adventure, spiritual |
| DJL | Darjeeling | Nature |
| GOA | Goa | Beach, nightlife |
| PDY | Pondicherry | Beach, culture |
| DEL | Delhi | Metro, history, food |
| BOM | Mumbai | Metro, food, nightlife |
| BLR | Bengaluru | Metro, food, nightlife |
| CCU | Kolkata | Food, culture |
| HYD | Hyderabad | Food, history |
| VNS | Varanasi | Spiritual, culture |
| MAA | Chennai | Food, culture, beach |

Origin and destination are both chosen from this list and must be different. This gives 210 directed city pairs.

### 5. User stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-01 | traveller | enter origin, destination, dates, group size and budget | I get a plan that fits my real trip |
| US-02 | traveller | say what I enjoy and how much time I want to spend out each day | the plan matches my interests and energy |
| US-03 | traveller | describe my preferences in my own words | I don't have to fiddle with sliders |
| US-04 | traveller | see two or three genuinely different plans side by side | I can choose between saving money and getting more out of the trip |
| US-05 | traveller | see a realistic day-by-day schedule with times and a map | I know the plan is actually doable |
| US-06 | traveller | see exactly where the money goes | I can trust the plan fits my budget |
| US-07 | traveller | see what I'd gain with more money or lose with less | I can decide whether to adjust my budget |
| US-08 | traveller | ask for changes in chat ("make day 2 relaxed", "cheaper hotel") | I can refine the plan without starting over |
| US-09 | traveller | ask why something was left out | I understand the plan's choices |
| US-10 | traveller | be told clearly when my budget is too low, and by how much | I don't waste time on an impossible request |
| US-11 | returning user | log in and find my saved trips, plans and chat | I can continue where I left off |
| US-12 | returning user | duplicate a trip with a different budget or dates | I can compare scenarios quickly |
| US-13 | evaluator | see measured evidence that the engine beats simpler approaches | I can judge the project's technical contribution |

### 6. Functional requirements

#### 6.1 Trip inputs

- **FR-001** The user selects an origin and a destination from the 15 supported cities. They must be different.
- **FR-002** The user selects a start date and an end date. The trip length (end − start + 1) is 2 to 7 days. The start date is at least tomorrow and at most 365 days ahead.
- **FR-003** The user enters a group size from 1 to 6 people.
- **FR-004** The user enters a budget either as a total or per person, in Indian rupees. A per-person budget is multiplied by group size to give the total. The total must be at least ₹2,000 per person and at most ₹10,00,000.
- **FR-005** The user sets preferences:
  - **Daily hours out:** hours per day they are willing to spend outside the hotel, 4 to 14 (default 9).
  - **Interest weights:** a weight from 0 to 5 for each of nine interests: nature, adventure, food, history/heritage, culture/art, spiritual, shopping, relaxation, nightlife. At least one weight is above 0.
  - **Pace:** relaxed, balanced (default) or packed.
  - **Stay comfort:** budget, mid (default) or premium.
  - **Transport modes:** each of train, bus and flight can be marked preferred, neutral (default) or avoided. At least one mode is not avoided.
  - **Avoid crowds:** on or off (default off).
- **FR-006** The user may describe preferences in free text. The AI layer converts it into the FR-005 fields. The converted values are shown to the user, who can adjust them before planning.
- **FR-007** For a logged-in user, the trip form is pre-filled from their saved preference profile.

#### 6.2 Plan generation

- **FR-010** For a valid request, the system produces at least one plan containing:
  - outbound transport (mode, class, duration, estimated cost),
  - return transport (same fields),
  - one hotel (name, tier, location, nights, rooms, estimated cost),
  - a day-by-day itinerary,
  - local travel between stops (mode, time, estimated cost),
  - a food allowance,
  - a budget breakdown,
  - the plan's trip value score.
- **FR-011** Every plan satisfies these hard constraints:
  - total estimated cost ≤ 90% of the budget (10% contingency),
  - no activity is scheduled on a day it is closed or outside its opening hours,
  - each day's time outside the hotel ≤ the user's daily hours out, after deducting travel to and from the destination on the first and last days,
  - the number of activities per day respects the pace limit,
  - no avoided transport mode is used,
  - locked activities are included and excluded activities are not (from chat refinement).
- **FR-012** If no plan can satisfy the constraints, the system says so and states the minimum total budget needed for these dates, group size and preferences, rounded up to the nearest ₹500.
- **FR-013** Every price is labelled as an estimate with the month the data was compiled. The budget breakdown categories (outbound, return, stay, local travel, entry fees, food, contingency) sum exactly to the plan total plus contingency.
- **FR-014** Each itinerary entry shows the activity name, start time, end time, entry fee, and the travel time, local mode and cost from the previous stop. Each day starts and ends at the hotel, except the first day may start at the arrival point and the last day may end at the departure point.
- **FR-015** The 10% contingency is shown as its own line in the budget breakdown.

#### 6.3 Variants and trade-offs

- **FR-020** The system produces up to three named variants:
  - **Saver:** the lowest cost that still reaches a set share of the best achievable trip value.
  - **Balanced:** the best trade-off between trip value and cost.
  - **Experience:** the highest trip value within the budget.

  At least one plan is always returned when the request is feasible.
- **FR-021** Two variants are shown only if they differ meaningfully: a different hotel, or at least 30% of activities different. Near-duplicates are merged and the user is told why fewer variants are shown.
- **FR-022** Variants are shown side by side with total cost, trip value, hotel, transport and highlights.
- **FR-023** For the selected plan, the system shows what changes with a budget 10% and 20% higher and lower. These figures come from re-running the engine.
- **FR-024** The system lists up to five activities that just missed the plan, each with its reason: over budget, not enough time, or closed or not open at a reachable time.
- **FR-025** All trade-off figures come from the engine. The LLM may phrase them but not compute them.

#### 6.4 AI assistant

- **FR-030** Each plan has a plain-language explanation of its main choices. The explanation mentions only items in the plan or in its near-miss list, and quotes only numbers the engine produced.
- **FR-031** After choosing a plan, the user can chat to refine it. Each message is mapped to one or more actions from this fixed set:
  - lock an activity,
  - exclude an activity,
  - change the budget,
  - change daily hours out (one day or all days),
  - change the hotel tier,
  - change a transport mode or class,
  - change the pace,
  - adjust interest weights,
  - move an activity to another day,
  - regenerate,
  - explain a choice.
- **FR-032** Every action that changes the plan re-runs the engine and saves a new plan version. The assistant then summarises what changed.
- **FR-033** A request outside the action set gets a short reply saying it can't be done, plus the closest supported action.
- **FR-034** "Why" questions are answered from engine data (near-miss reasons, constraint that blocked an item, cost and value figures).
- **FR-035** If the LLM is unavailable, plans still generate. Explanations are omitted with a notice, and chat shows that it is temporarily unavailable.

#### 6.5 Accounts and saved data

- **FR-040** Users sign up and log in with email and password.
- **FR-041** Users can log out. Sessions expire after 7 days.
- **FR-042** Users can save and edit a preference profile (the FR-005 fields).
- **FR-043** Each generated trip is saved with its inputs and all variants.
- **FR-044** The selected plan keeps a version history. The user can restore an earlier version, which becomes the newest version.
- **FR-045** The chat history is saved per trip.
- **FR-046** **My Trips** lists upcoming and past trips. The user can rename, duplicate (same inputs, editable before re-planning) and delete a trip. Delete asks for confirmation on the page.
- **FR-047** A user can never see or change another user's data.

#### 6.6 Pages and interface

- **FR-050** The app has seven pages:
  1. Landing
  2. Sign up / Log in
  3. New trip form
  4. Plan comparison
  5. Plan detail, with the chat panel
  6. My Trips
  7. Profile and preferences
- **FR-051** The plan detail page shows a map with the hotel, each day's stops and each day's route in a distinct colour.
- **FR-052** The plan detail page shows the budget breakdown as a chart and as a table.
- **FR-053** All pages are usable at widths from 360 px (phone) to desktop, with no horizontal scrolling.

#### 6.7 Data

- **FR-060** The app ships with curated data for the 15 cities: city access hubs, intercity distances and travel times, fare rates, attractions, hotels, food allowances, local transport rates and local travel times. Feature 001 defines it in full.
- **FR-061** Each curated record stores its source and the date it was checked.
- **FR-062** The app shows the dataset's compilation month next to prices ("Estimated prices, compiled Nov 2026").

#### 6.8 Evaluation

- **FR-070** An evaluation harness runs Tripwise, a greedy baseline and an LLM-only baseline on a fixed set of 30 test trips. It checks all three with the same validator and reports constraint violations, trip value, budget use, share of time spent travelling and solve time.
- **FR-071** A test set of 50 hand-written chat requests, each with its expected actions, measures the assistant's intent accuracy.

### 7. Non-functional requirements

- **NFR-001 Planning speed:** generating all variants for one request takes ≤ 5 s at the 95th percentile on the deployed backend, measured over the 30 test trips. Explanations may load after the plans appear.
- **NFR-002 Chat speed:** a chat action, including the re-solve, completes in ≤ 8 s at the 95th percentile.
- **NFR-003 Security:**
  - bcrypt password hashing,
  - JWT sessions with 7-day expiry,
  - HTTPS only,
  - CORS limited to the frontend's domain,
  - secrets only in environment variables.
- **NFR-004 Cost:** only free tiers are used: Vercel Hobby, Neon free tier, Azure for Students, Groq free tier, OpenRouteService free tier.
- **NFR-005 LLM usage:** at most one Groq call to explain all variants of a request, and at most two Groq calls per chat message.
- **NFR-006 Browsers:** current versions of Chrome, Edge, Firefox and Safari, on desktop and on mobile.
- **NFR-007 Accessibility:** every form control has a label, every action works by keyboard, and text meets WCAG AA contrast.
- **NFR-008 Repeatability:** the same request on the same deployment and dataset version returns the same plans.
- **NFR-009 Configurability:** all value weights, limits and solver time limits are in one configuration file.
- **NFR-010 Data quality:** the data validation script reports zero errors on the shipped dataset.

### 8. Assumptions

- **A-01** Prices are typical estimates for the compilation month. They are not live quotes, and seasonal price changes are not modelled in v1.
- **A-02** Hotel rooms hold two people, so rooms = ⌈group size ÷ 2⌉.
- **A-03** Entry fees use the Indian adult rate. Child and foreign-national rates are not modelled.
- **A-04** Each attraction has one opening interval per open day, and the same interval on every day it opens.
- **A-05** Local travel within a city is by auto-rickshaw (budget comfort) or cab (mid and premium comfort). Metro and city buses are not modelled in v1.
- **A-06** Times are Indian Standard Time, in 24-hour format.
- **A-07** Long journeys can be taken overnight. Feature 002 defines exactly how travel time reduces the first and last days.
- **A-08** The premium daily food allowance is 2 × the mid allowance. No published source gives a premium figure, so this is an assumption (Feature 001 Spec §5.7).

### 9. Out of scope

- Real bookings, payments or live prices.
- Cities beyond the 15, and multi-city trips.
- A native mobile app.
- Seasonal or dynamic pricing, weather and festival calendars.
- Child or foreign-national pricing.
- Sharing trips with other users, or collaborative editing.
- Social login (Google, etc.). It may be added later through a spec amendment.
- Languages other than English.

### 10. Feature breakdown

| Spec | Feature | Covers |
|---|---|---|
| 001 | City data | FR-060–062, NFR-010 |
| 002 | Optimization engine (single plan) | FR-010–015, NFR-008, NFR-009 |
| 003 | Variants and trade-offs | FR-020–025, NFR-001 |
| 004 | Accounts and saved data | FR-040–047, NFR-003 |
| 005 | Trip planning API | FR-001–005, FR-007, API contracts for all features |
| 006 | Frontend | FR-050–053, FR-062 display, NFR-006, NFR-007 |
| 007 | AI layer | FR-006, FR-030–035, NFR-002, NFR-005 |
| 008 | Evaluation | FR-070, FR-071 |
| 009 | Deployment | NFR-001 and NFR-002 measured on the live system, end-to-end check |

Build order: 001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009.

### 11. Success criteria for the project

1. All acceptance tests in Features 001–009 pass and are recorded in Part D (Traceability).
2. On the 30 test trips, Tripwise plans have zero constraint violations. The results table also reports violation rates for the greedy and LLM-only baselines.
3. The deployed app completes a full trip (form → variants → refine in chat → saved in My Trips) for a new user.
4. At least three test users rate the plans' realism, and the ratings are recorded.

### 12. Glossary

| Term | Meaning |
|---|---|
| Plan | One complete trip proposal: transport, hotel, itinerary, local travel, food and budget |
| Variant | One of Saver, Balanced or Experience for the same request |
| Plan version | A saved state of the selected plan. Each chat change or restore creates one |
| Trip value | The engine's score of how well a plan matches the user, defined in Feature 002 |
| Usable budget | 90% of the total budget. The remaining 10% is contingency |
| Daily hours out | Maximum hours per day the user spends outside the hotel |
| Access hub | The railway station, bus stand or airport used to reach a city |
| Near-miss | An activity that was a strong candidate but not chosen, with its reason |
| Cut | A constraint added to the selection stage when the scheduling stage cannot fit an activity |
| Validator | Independent code that checks any plan against all hard constraints |

### 13. Open questions

None blocking. Decisions deferred to Part C:

- the exact Groq model (Feature 007),
- the exact value-function weights, which are tuned during Feature 002 and recorded in its config.

---

## Part C — Features

Build order: 001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009. A feature's Plan and Tasks are added only after its Spec is approved.

### Feature 001 — City data

Status: Spec **Approved** · Plan **Approved** · Tasks **Approved**
Traces to: FR-060, FR-061, FR-062, NFR-010 · Constitution Article III

#### 001 Spec

##### 1. Goal

Produce a curated, validated dataset for the 15 supported cities. It must hold everything the engine needs to price and schedule a trip: how to get between cities, what each journey costs, what to do in each city, where to stay, what food and local travel cost, and how long it takes to move between places inside a city.

The dataset lives as version-controlled CSV/JSON files in `data/curated/` and is loaded into Neon Postgres by a script. The files are the source of truth; the database is a loaded copy.

##### 2. Scope

**In scope:** cities and access hubs, intercity pairs, fare rates, attractions, hotels, food allowances, local transport rates, intra-city travel-time matrices, a validation script and a loader script.

**Out of scope:** live prices, seasonal prices, metro and city-bus networks, restaurants as separate entities (food is an allowance), user-generated data.

##### 3. Conventions

- **Money:** whole Indian rupees (integer).
- **Distance:** kilometres (decimal, 1 place). **Durations:** minutes (integer).
- **Times:** `HH:MM`, 24-hour, IST.
- **Weekdays:** integers 0–6, with 0 = Monday.
- **Coordinates:** WGS84 decimal degrees, 5 places.
- **IDs:** city codes from Part B §4 (`JAI`, `AGR`, …). Other IDs are `<CITY>-<TYPE>-<NN>`, for example `JAI-A-07` (attraction) and `JAI-H-03` (hotel).
- **Provenance:** every curated row has `source` (URL or short citation) and `checked_on` (date). `checked_on` is the date the source page was fetched, for values read directly from an opened page whose evidence (the page extract or API response) is saved in `data/raw/`. A value derived from such evidence (a fit, a conversion, a lookup) takes the latest fetch date of its inputs. `checked_on` is empty only for rows still marked TODO, which fail validation.
- **City centre:** the main tourist or commercial core of the city, chosen by hand. The reason is recorded in `source`.
- **Dataset version:** `data/curated/VERSION` holds the version (for example `1.0`) and the compilation month (for example `2026-11`). This is the month shown to users (FR-062).

##### 4. Interest tags

Exactly these nine values are allowed, matching FR-005:

`nature`, `adventure`, `food`, `history`, `culture`, `spiritual`, `shopping`, `relaxation`, `nightlife`

##### 5. Entities

###### 5.1 `cities.csv` — 15 rows

| Field | Type | Rule |
|---|---|---|
| city_id | text | One of the 15 codes |
| name | text | |
| lat, lon | decimal | City centre (section 3), with the reason in `source` |
| traffic_factor | decimal | Multiplier on free-flow drive times, 1.0–2.0. Suggested: 1.4 for DEL, BOM, BLR, CCU, HYD, MAA; 1.2 for JAI, AGR, VNS, GOA, PDY; 1.1 for the rest |
| food_multiplier | decimal | Multiplier on base food allowance, 0.6–2.2. A city with no cost-of-living source uses 1.0, marked as an approximation in `source` |
| source, checked_on | | |

###### 5.2 `hubs.csv` — access points per city

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

###### 5.3 `city_pairs.csv` — 105 unordered pairs

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
| rail_km_approx | bool | True when rail_km was copied from road_km |
| train_minutes_approx, bus_minutes_approx, flight_minutes_approx | bool | True when that duration came from the fallback formula |
| source, checked_on | | |

**Rule:** the engine adds 90 minutes airport overhead to every flight, and the hub access time (5.2) to every journey at both ends. These are not stored in `*_minutes`.

###### 5.4 `fare_rates.csv` — one row per mode and class

| mode | class | Meaning |
|---|---|---|
| train | SL | Sleeper |
| train | 3A | AC 3-tier |
| train | 2A | AC 2-tier |
| bus | ACS | AC sleeper |
| flight | Y | Economy |

| Field | Type | Rule |
|---|---|---|
| mode, class | enum | As above |
| base_fare | int | Fixed charge per person per journey (reservation, fees) |
| per_km | decimal | Per person per km, on rail_km / road_km / air_km |
| min_fare | int | Floor per person |
| comfort_value | decimal | 0–1, used by the engine's value function. Defaults: SL 0.2, 3A 0.6, 2A 0.8, ACS 0.5, Y 0.9 |
| source, checked_on | | Published fare chart or a sample of real fares, with the method recorded |

**Fare formula** (per person, one way) = max(min_fare, base_fare + per_km × distance).

**Sanity bounds** for validation. These only catch typos and are not price claims:

| class | per_km |
|---|---|
| SL | 0.2–1.0 |
| 3A | 0.5–2.2 |
| 2A | 0.8–3.2 |
| ACS | 1.5–3.5 |
| Y | 2.0–9.0, with base_fare 1,000–6,000 |

###### 5.5 `attractions/<CITY>.csv` — 25 to 40 per city

One file per city (for example `attractions/JAI.csv`), so each city can be curated and reviewed on its own.

| Field | Type | Rule |
|---|---|---|
| attraction_id | text | `<CITY>-A-<NN>` |
| city_id | text | |
| name | text | |
| lat, lon | decimal | Within 60 km of the city centre |
| visit_minutes | int | Typical visit, 20–480. Default by place type (below) when no source gives a duration |
| visit_approx | bool | True when visit_minutes is the place-type default |
| open_time, close_time | HH:MM | Opening and closing time; a visit must finish by close_time. open < close, and close − open ≥ visit_minutes. Use 00:00–23:59 for always open. From the ASI or the official site first, otherwise the place-type default (below) |
| closed_weekdays | list of int | For example `[0]` for closed Mondays; empty if open daily |
| hours_approx | bool | True when open_time, close_time and closed_weekdays are the place-type default |
| entry_fee | int | Indian adult, per person; 0 allowed. From the ASI or the official site first (a fee the user read from an official booking page counts as official, recorded in `source` as "read by user from <url>, <date>"); otherwise the median of at least 2 independent secondary sources, rounded to whole rupees, with their URLs saved in `data/raw/attractions/fee_secondary.csv`; otherwise 0 for temple, viewpoint, market and beach (noted in `source`); monument, museum and activity have no default and stay TODO |
| fee_approx | bool | True when entry_fee is the median of secondary sources |
| tags | list | 1–3 interest tags from section 4. The first is the primary tag |
| rating | decimal | 1.0–5.0, popularity within the city (see **Rating and crowd level** below) |
| outdoor | bool | |
| crowd_level | enum | `low`, `medium`, `high`: popularity terciles within the city |
| fixed_slot | bool | True for events at a set time, such as Ganga Aarti. Then open_time/close_time is the event window and visit_minutes fits inside it |
| source, checked_on | | Opening hours and fee source; may differ from seed source |

**Place types.** Each attraction is given one place type during drafting (kept in `data/raw/attractions/`), used only for defaults. Other kinds map onto these: fort, palace, tomb, ruins → monument; gallery, zoo → museum; mosque, church, gurudwara, ghat → temple; lake, garden, park, waterfall → viewpoint; mall, bazaar → market; trek, rafting, safari, show → activity.

| Place type | Default visit_minutes | Default hours | Default closed |
|---|---|---|---|
| monument | 90 | 09:00–17:00 | — |
| museum | 120 | 10:00–17:00 | Monday |
| temple | 45 | 06:00–20:00 | — |
| viewpoint | 30 | 06:00–18:00 | — |
| market | 90 | 10:00–21:00 | — |
| beach | 120 | 06:00–19:00 | — |
| activity | 180 | 09:00–17:00 | — |

**Rating and crowd level.**

- Popularity is the attraction's English Wikipedia pageviews over the 12 complete months before compilation (Wikimedia REST API, all access, user agents). Within each city, rating = 1 + 4 × (ln v − ln v_min) ÷ (ln v_max − ln v_min) over the attractions that have pageviews, rounded to 1 decimal (3.0 if they all have the same count).
- An attraction with no Wikipedia article uses its OpenTripMap `rate` instead: 1 → 2.0, 2 → 3.0, 3 → 4.0 (the `h` heritage flag is ignored).
- crowd_level: the city's attractions sorted by rating are split into thirds: bottom `low`, middle `medium`, top `high`.
- Every pageview and OpenTripMap lookup is saved in `data/raw/`.

**Coverage rules:**

- Each city has at least 25 attractions.
- Every interest tag that fits the city's character (Part B §4) appears on at least 3 of its attractions.
- At least 5 attractions per city have `entry_fee = 0`.

###### 5.6 `hotels.csv` — 3 tiers × 2–4 hotels per city

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

Aim for 3–4 hotels per tier. A tier may have 2 when no more can be found within its band, with the reason in `source`.

Hotels within a city should spread across at least two areas so location matters.

###### 5.7 `food.csv`

Three rows, one per comfort level, giving `base_per_person_per_day`. City cost = base × the city's `food_multiplier`. The premium row is 2 × the mid row (assumption A-08).

###### 5.8 `local_transport.csv` — 2 rows per city

| Field | Type | Rule |
|---|---|---|
| city_id | text | |
| mode | enum | `auto`, `cab` |
| min_fare | int | Minimum fare per vehicle, covering the first `min_km` |
| min_km | decimal | Distance covered by the minimum fare |
| per_km | decimal | Per vehicle, for each km beyond `min_km` |
| capacity | int | People per vehicle: auto 3, cab 4 |
| approx | bool | True when the tariff was not notified for this city (see below) |
| source, checked_on | | |

Ride cost = (min_fare + per_km × max(0, km − min_km)) × ⌈people ÷ capacity⌉.

**Missing tariffs:** a city with no notified tariff of its own uses its state's tariff: a statewide notification (`approx = false`), or failing that another city's notified tariff in the same state (`approx = true`). If the state has none either, the city uses the median `min_fare`, `min_km` and `per_km` of the cities that have a tariff for that mode, with `approx = true`.

###### 5.9 `matrices/<CITY>.json` — intra-city travel

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

##### 6. Collection workflow

1. **Seed attractions:** a script queries OpenTripMap (and OpenStreetMap through Overpass where useful) for each city and writes candidates to `data/raw/seed_<CITY>.json`.
2. **Curate:** choose 25–40 attractions per city. Fill visit time, hours, closed days, fee, tags, rating, crowd level and sources by hand, checking official sites where they exist.
3. **Hubs, pairs and fares:** fill `hubs.csv` and `fare_rates.csv` by hand. A script computes `road_km` and `air_km` and the formula fallbacks for `city_pairs.csv`, then known published times are entered as overrides.
4. **Hotels, food and local transport:** fill by hand from public listings, recording sources.
5. **Matrices:** a script calls OpenRouteService once per city and writes `matrices/<CITY>.json`.
6. **Validate:** `python -m datatools.validate` must report 0 errors.
7. **Load:** `python -m datatools.load` truncates and reloads the Neon tables inside one transaction, and records the dataset version.

##### 7. Requirements

- **DATA-FR-01** The dataset contains exactly 15 cities with the fields in 5.1. (FR-060)
- **DATA-FR-02** Every city has at least one hub, and every hub has access distance, time and cost. (FR-060)
- **DATA-FR-03** `city_pairs.csv` has exactly 105 unordered pairs. Every pair has at least one available mode. Every available mode has a positive duration. (FR-060)
- **DATA-FR-04** `fare_rates.csv` has the 5 mode-class rows, each within its sanity bounds. (FR-060)
- **DATA-FR-05** Every city meets the attraction coverage rules in 5.5. (FR-060)
- **DATA-FR-06** Every city has 2–4 hotels in each tier, within the tier's price band. (FR-060)
- **DATA-FR-07** Every city has a complete matrix whose nodes are exactly its hotels, attractions and hubs. All off-diagonal values are positive, and the diagonal is 0. (FR-060)
- **DATA-FR-08** Every curated row has a non-empty `source` and a valid `checked_on` date. (FR-061)
- **DATA-FR-09** `data/curated/VERSION` exists, and the loader writes its version and compilation month to the database. (FR-062)
- **DATA-FR-10** The validator checks every rule in sections 3–5 and 7. It prints each error with file, row and field, and exits non-zero if any error is found. (NFR-010)
- **DATA-FR-11** The loader is all-or-nothing: if any insert fails, the database keeps its previous data.
- **DATA-FR-12** Every approximation used (`rail_km_approx`, formula-derived durations) is flagged in the row so the evaluation can report how much of the data is approximate. (Constitution III.3)

##### 8. Acceptance tests

| ID | Test | Pass when |
|---|---|---|
| DATA-AT-01 | Run `python -m datatools.validate` on the shipped dataset | Exit code 0, "0 errors" |
| DATA-AT-02 | Validator self-test: run it on fixtures that each break one rule (missing source, bad tag, open ≥ close, unknown city, price outside band, missing matrix node, pair with no mode) | Each fixture produces exactly the expected error, and the run exits non-zero |
| DATA-AT-03 | Run `python -m datatools.load` against Neon | Row counts in the database equal the CSV counts. The version table shows the VERSION contents |
| DATA-AT-04 | Make the loader fail partway (bad row injected in a test copy) | Previous database contents unchanged |
| DATA-AT-05 | Spot check: pick 20 random attractions, 10 random hotels and every fare row, and re-check them against their source | At least 18 of 20 attractions, 10 of 10 hotels and every fare row match. Record results in `data/spot_check.md` |
| DATA-AT-06 | Count report: `python -m datatools.report` | Prints per-city counts, and the share of pairs with approximate rail distance and with formula durations |

##### 9. Risks

- **Time:** curating ~500 attractions is the largest manual task in the project. Mitigation: start on Day 2, curate the 5 cities used most in test trips first, and use the seed script to pre-fill names, coordinates and tags.
- **Opening hours accuracy:** OpenStreetMap hours are incomplete. Mitigation: prefer official sites; when hours can't be confirmed, use the site's commonly stated hours and record that in `source`.
- **OpenRouteService limits:** the free tier caps requests per day and matrix size. Mitigation: one matrix call per city (about 55 nodes), with cached responses.

#### 001 Plan

##### 1. Approach

The dataset is a set of plain CSV and JSON files in `data/curated/`, edited by hand and by small scripts, and kept in git. A Python package `datatools/` holds the scripts: seeding, computing pairs and matrices, validating, loading into Neon, and reporting.

The work splits into three kinds:

1. **Scripted:** seed attraction candidates, compute distances and fallback durations for city pairs, fetch intra-city matrices. These are repeatable and cache their API responses.
2. **Hand-curated:** hubs, fares, attractions, hotels, food, local transport. Every row gets a source and a check date.
3. **Checking:** the validator encodes every rule in the spec. Nothing is loaded into Neon unless it reports 0 errors.

**Package name.** The spec writes `python -m data.validate`. A Python package called `data` that also holds the CSV files mixes code and data, and the name is easy to clash with. The code therefore lives in `datatools/`, and the commands become `python -m datatools.validate`, `python -m datatools.load` and `python -m datatools.report`. The 001 Spec is amended to match (see Changelog).

**Drafting attractions with Claude.** Claude may draft attraction rows from the seed candidates to save typing. Values come only from pages actually opened; `checked_on` follows the provenance rule in 001 Spec §3, and a row whose value could not be read from a page stays TODO with `checked_on` empty, so it fails validation (Constitution III.4). The enlarged spot check (DATA-AT-05) is the human check on drafted rows.

**Curation scripts.** The scripts that build the hand-curated files from saved evidence live in `datatools/curation/` and are committed, so every derived value (fits, conversions, tier choices) can be re-run.

**Rejected alternatives:**

- A spreadsheet as the master copy: harder to diff and validate in git.
- Storing data only in Postgres: no review history, and harder to rebuild.

##### 2. Files

###### 2.1 Data (`data/`)

| Path | Contents | Spec |
|---|---|---|
| `data/curated/VERSION` | Two lines: `version=1.0` and `compiled=2026-11` | 3, DATA-FR-09 |
| `data/curated/cities.csv` | 15 rows | 5.1 |
| `data/curated/hubs.csv` | 1–3 rows per city | 5.2 |
| `data/curated/city_pairs.csv` | 105 rows | 5.3 |
| `data/curated/fare_rates.csv` | 5 rows | 5.4 |
| `data/curated/attractions/<CITY>.csv` | 25–40 rows each, 15 files | 5.5 |
| `data/curated/hotels.csv` | 9–12 rows per city | 5.6 |
| `data/curated/food.csv` | 3 rows | 5.7 |
| `data/curated/local_transport.csv` | 2 rows per city | 5.8 |
| `data/curated/matrices/<CITY>.json` | 15 files | 5.9 |
| `data/raw/seed/<CITY>.json` | Seed candidates (kept in git) | 6.1 |
| `data/raw/ors/` | Cached OpenRouteService responses (git-ignored) | 5.9 |
| `data/spot_check.md` | Results of DATA-AT-05 | 8 |

**CSV conventions:**

- UTF-8, comma-separated, header row, no index column.
- Lists use `;` inside one cell: `closed_weekdays` = `0;3`, `tags` = `history;culture`.
- Booleans are `true` / `false`.
- Empty cell means missing. The validator rejects it unless the field is optional.

###### 2.2 Code (`datatools/`)

| Path | Responsibility | Requirements |
|---|---|---|
| `datatools/__init__.py` | Package marker | |
| `datatools/rules.py` | City codes, interest tags, enums, sanity bounds, coverage thresholds: every constant from the spec, in one place | DATA-FR-01–08 |
| `datatools/models.py` | Pydantic models, one per entity, with field-level checks (types, ranges, formats) | DATA-FR-10 |
| `datatools/io.py` | Read and write the CSV/JSON files into the models; list-cell parsing | |
| `datatools/geo.py` | Haversine distance; OpenRouteService client (matrix call, response cache) | DATA-FR-03, 07 |
| `datatools/seed.py` | `python -m datatools.seed <CITY>`: fetch candidates from OpenTripMap (fallback: Overpass) into `data/raw/seed/<CITY>.json` | Spec 6.1 |
| `datatools/draft.py` | `python -m datatools.draft <CITY>`: turn seed candidates into a draft `attractions/<CITY>.csv`, with name, coordinates, suggested tags, place type, pageview-based rating and crowd level filled, the rest blank | Spec 5.5, 6.2 |
| `datatools/pairs.py` | `python -m datatools.pairs`: compute road_km (ORS, bus hubs), air_km (haversine, flight hubs), availability flags and fallback durations. Keeps any hand-entered override columns | DATA-FR-03, 12 |
| `datatools/matrices.py` | `python -m datatools.matrices [CITY]`: build `matrices/<CITY>.json` from hotels, attractions and hubs | DATA-FR-07 |
| `datatools/validate.py` | `python -m datatools.validate [--data DIR]`: run every rule; print `file:row:field: message`; exit 1 on any error | DATA-FR-10 |
| `datatools/load.py` | `python -m datatools.load`: validate first, then reload Neon in one transaction | DATA-FR-09, 11 |
| `datatools/report.py` | `python -m datatools.report`: per-city counts, tag coverage, approximation shares | DATA-FR-12, DATA-AT-06 |
| `datatools/sql/schema.sql` | Table definitions | DATA-FR-11 |
| `datatools/tests/` | pytest tests and broken fixtures | DATA-AT-02, 04 |
| `datatools/curation/` | Scripts that build cities, food, hubs, fares, local transport and hotels from evidence in `data/raw/`; the fixture generator | Spec 6.3, 6.4 |

##### 3. Data model in Postgres

All tables live in schema `ref` (reference data), separate from user data in Feature 004.

```sql
CREATE SCHEMA IF NOT EXISTS ref;

CREATE TABLE ref.data_version (version text PRIMARY KEY, compiled text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE ref.cities (city_id char(3) PRIMARY KEY, name text NOT NULL, lat numeric(8,5), lon numeric(8,5),
  traffic_factor numeric(3,2) NOT NULL, food_multiplier numeric(3,2) NOT NULL, source text NOT NULL, checked_on date NOT NULL);

CREATE TABLE ref.hubs (city_id char(3) REFERENCES ref.cities, mode text CHECK (mode IN ('train','bus','flight')),
  hub_name text NOT NULL, hub_code text, lat numeric(8,5), lon numeric(8,5), access_km numeric(6,1) NOT NULL,
  access_minutes int NOT NULL, access_cost_per_vehicle int NOT NULL, source text NOT NULL, checked_on date NOT NULL,
  PRIMARY KEY (city_id, mode));

-- 210 directed rows, expanded from the 105 unordered CSV rows
CREATE TABLE ref.city_pairs (from_city char(3) REFERENCES ref.cities, to_city char(3) REFERENCES ref.cities,
  road_km numeric(7,1), rail_km numeric(7,1), air_km numeric(7,1),
  train_available bool NOT NULL, bus_available bool NOT NULL, flight_available bool NOT NULL,
  train_minutes int, bus_minutes int, flight_minutes int, rail_km_approx bool NOT NULL,
  train_minutes_approx bool NOT NULL, bus_minutes_approx bool NOT NULL, flight_minutes_approx bool NOT NULL,
  source text NOT NULL, checked_on date NOT NULL, PRIMARY KEY (from_city, to_city));

CREATE TABLE ref.fare_rates (mode text, class text, base_fare int NOT NULL, per_km numeric(5,2) NOT NULL,
  min_fare int NOT NULL, comfort_value numeric(3,2) NOT NULL, source text NOT NULL, checked_on date NOT NULL,
  PRIMARY KEY (mode, class));

CREATE TABLE ref.attractions (attraction_id text PRIMARY KEY, city_id char(3) REFERENCES ref.cities, name text NOT NULL,
  lat numeric(8,5), lon numeric(8,5), visit_minutes int NOT NULL, open_time time NOT NULL, close_time time NOT NULL,
  closed_weekdays int[] NOT NULL, entry_fee int NOT NULL, tags text[] NOT NULL, rating numeric(2,1) NOT NULL,
  outdoor bool NOT NULL, crowd_level text NOT NULL, fixed_slot bool NOT NULL, source text NOT NULL, checked_on date NOT NULL);

CREATE TABLE ref.hotels (hotel_id text PRIMARY KEY, city_id char(3) REFERENCES ref.cities, name text NOT NULL,
  tier text NOT NULL, lat numeric(8,5), lon numeric(8,5), price_per_room_night int NOT NULL,
  source text NOT NULL, checked_on date NOT NULL);

CREATE TABLE ref.food (comfort text PRIMARY KEY, base_per_person_per_day int NOT NULL, source text NOT NULL, checked_on date NOT NULL);

CREATE TABLE ref.local_transport (city_id char(3) REFERENCES ref.cities, mode text, min_fare int NOT NULL,
  min_km numeric(4,1) NOT NULL, per_km numeric(5,2) NOT NULL, capacity int NOT NULL, approx bool NOT NULL,
  source text NOT NULL, checked_on date NOT NULL,
  PRIMARY KEY (city_id, mode));

-- matrices stored long-form
CREATE TABLE ref.travel_matrix (city_id char(3) REFERENCES ref.cities, from_node text, to_node text,
  km numeric(6,1) NOT NULL, minutes_free_flow int NOT NULL, PRIMARY KEY (city_id, from_node, to_node));
```

**Spec clarification:** 001 Spec §5.3 had a single `rail_km_approx` flag. DATA-FR-12 also asks for formula-derived durations to be flagged, so `city_pairs.csv` gets three more boolean columns: `train_minutes_approx`, `bus_minutes_approx` and `flight_minutes_approx`. The 001 Spec is amended to list them.

**Loader** (`load.py`):

1. Run the validator and stop on errors.
2. Open one transaction.
3. `TRUNCATE` all `ref` tables.
4. Bulk insert in dependency order.
5. Insert the `data_version` row.
6. Commit.

Any exception rolls the whole transaction back (DATA-FR-11).

##### 4. Validator design

Two passes:

1. **Row checks**, through Pydantic models: types, ranges, enums, time format, `open < close`, `close − open ≥ visit_minutes`, tag values, 1–3 tags, non-empty `source`, valid `checked_on` that is not in the future.
2. **Dataset checks**, across files:
   - exactly 15 cities, with the expected codes,
   - every city has ≥ 1 hub,
   - exactly 105 pairs with `city_a < city_b` and no duplicates; each has ≥ 1 mode, and a positive duration for every available mode,
   - a pair mode is available only if both cities have a hub for it,
   - 5 fare rows within sanity bounds,
   - per-city attraction coverage (≥ 25, tag coverage for the city's character, ≥ 5 free),
   - hotels: 2–4 per tier per city, within price bands and within 25 km of the centre,
   - attractions within 60 km of the centre,
   - unique IDs, with IDs matching their city prefix,
   - each matrix's nodes = that city's hotels + attractions + `<CITY>-HUB-<mode>` for each hub; square, diagonal 0, off-diagonal > 0,
   - `VERSION` present and well-formed.

**City character → required tags** (for the coverage rule), kept in `rules.py`:

| City | Tags that need ≥ 3 attractions |
|---|---|
| JAI, AGR, HMP | history, culture |
| MUN, DJL | nature, relaxation |
| RSH | nature, adventure, spiritual |
| GOA | relaxation, nightlife, nature |
| PDY | relaxation, culture |
| DEL | history, food, shopping |
| BOM, BLR | food, nightlife, culture |
| CCU | food, culture |
| HYD | food, history |
| VNS | spiritual, culture |
| MAA | food, culture, relaxation |

Output format: `attractions/JAI.csv:14:close_time: must be later than open_time (09:00 ≥ 08:30)`. The run ends with `N errors, M warnings`. Warnings never fail the run; example: hotels in one city all within 2 km of each other.

##### 5. Dependencies

Installed into the shared venv `backend\.venv` from `datatools/requirements.txt`:

| Package | Use |
|---|---|
| pydantic ≥ 2.6 | Row models and checks |
| psycopg[binary] ≥ 3.1 | Postgres loader |
| requests ≥ 2.31 | OpenTripMap, Overpass and ORS calls |
| python-dotenv ≥ 1.0 | Read `.env` |
| pytest ≥ 8.0 | Tests |

No pandas. The files are small, and the standard `csv` module plus Pydantic is enough.

##### 6. Test strategy

| Acceptance test | How |
|---|---|
| DATA-AT-01 | `python -m datatools.validate` in the terminal; also a pytest test that runs the validator on `data/curated` and expects 0 errors |
| DATA-AT-02 | `datatools/tests/fixtures/valid/`: a small valid mini-dataset (2 cities, fake data). Each broken case is generated by the test: it copies the valid set to a temporary directory and breaks one rule. The tests assert the exact file, row, field and error code (below) for each |
| DATA-AT-03 | `python -m datatools.load`, then `python -m datatools.report --db`, which compares database row counts with CSV counts |
| DATA-AT-04 | pytest against a throwaway Neon branch: load a valid set, then load a set with a row that breaks a database constraint; assert row counts unchanged |
| DATA-AT-05 | Manual. `python -m datatools.report --sample 20 10 --seed 7` picks the attractions and hotels; all fare rows are checked; results go in `data/spot_check.md` |
| DATA-AT-06 | `python -m datatools.report` |

For the mini-dataset fixtures, the validator takes `--data DIR` and a `--cities JAI,AGR` option, so the "exactly 15 cities" rule can be relaxed in tests only.

**Validator error codes.** Every finding carries a stable code, which the tests assert. The printed line stays `file:row:field: message`.

| Group | Codes |
|---|---|
| File and format | `missing_file`, `bad_header`, `bad_json`, `bad_version`, `unexpected_file`, `wrong_file` |
| Cell values | `missing_value`, `out_of_range`, `bad_enum`, `bad_format`, `bad_length`, `bad_number`, `bad_bool`, `bad_precision`, `bad_time`, `bad_date`, `future_date`, `duplicate_value` |
| Provenance | `missing_source`, `missing_checked_on` |
| Cities and IDs | `unknown_city`, `missing_city`, `duplicate_id`, `id_city_mismatch`, `too_far` |
| Hubs and pairs | `city_no_hub`, `missing_pair`, `pair_order`, `pair_no_mode`, `pair_mode_without_hub`, `missing_duration`, `bus_too_far`, `flight_too_short`, `approx_mismatch` |
| Fares | `missing_fare`, `fare_out_of_bounds` |
| Attractions | `open_not_before_close`, `visit_exceeds_hours`, `bad_weekday`, `bad_tag`, `bad_tag_count`, `bad_attraction_count`, `too_few_free`, `tag_coverage` |
| Hotels, food, local transport | `price_out_of_band`, `bad_hotel_count`, `missing_row`, `bad_capacity` |
| Matrices | `bad_matrix`, `matrix_missing_node`, `matrix_extra_node`, `matrix_shape`, `matrix_diagonal`, `matrix_nonpositive` |
| Warning only | `hotels_clustered` |

To avoid knock-on errors, count and coverage checks for a city are skipped while one of that city's rows in the same file cannot be parsed, and matrix node checks skip node kinds whose source file cannot be read.

##### 7. Order of work

1. Package skeleton, rules, models, and the validator on fixtures (so every later file is checked as it is written).
2. Cities, hubs and fares by hand, then `pairs.py`.
3. Hotels, food and local transport by hand.
4. Attractions: seed → draft → curate, five priority cities first: JAI, DEL, GOA, BLR, VNS.
5. Remaining 10 cities.
6. Matrices.
7. Schema, loader and report.
8. Acceptance tests and spot check.

#### 001 Tasks

Work top to bottom and tick `[x]` when a task is done and its check passes. "Check" says how you know it's finished.

##### Setup
- [x] **T01** Create the `datatools/` package skeleton, `datatools/requirements.txt` and `datatools/tests/`; create `backend\.venv` and install the requirements. · Check: `python -c "import datatools"` works.
- [x] **T02** Write `datatools/rules.py`: city codes, the 9 tags, enums, sanity bounds, price bands, coverage thresholds and city → required tags, all taken from 001 spec and plan. · serves DATA-FR-01–08
- [x] **T03** Write `datatools/models.py` (Pydantic models for every entity, with row checks) and `datatools/io.py` (CSV/JSON reading, `;` list cells). · serves DATA-FR-10
- [x] **T04** Write `datatools/validate.py`, with both passes, `--data` and `--cities` options, `file:row:field` messages and exit codes. · serves DATA-FR-10
- [x] **T05** Build the fixture mini-dataset (2 cities, valid); write pytest tests that generate one broken copy per rule and assert each error. · Check: DATA-AT-02 passes.

##### Hand-curated base files
- [x] **T06** Create `data/curated/VERSION`, `cities.csv` (15 rows) and `food.csv` (3 rows), with sources. · serves DATA-FR-01, 09
- [x] **T07** Create `hubs.csv`, verifying the outside-city hubs listed in spec 5.2. · serves DATA-FR-02
- [x] **T08** Create `fare_rates.csv` (5 rows) from samples of real fares, recording the method. · serves DATA-FR-04
- [x] **T09** Create `local_transport.csv` (auto and cab for 15 cities). · serves DATA-FR-06 (local travel inputs)
- [x] **T10** Create `hotels.csv`: 2–4 per tier per city (3–4 where possible), spread over at least two areas. · serves DATA-FR-06

##### Scripted files
- [x] **T11** Write `datatools/geo.py`: haversine and an ORS client with a response cache in `data/raw/ors/`.
- [x] **T12** Write `datatools/pairs.py` and generate `city_pairs.csv` (105 rows); then enter known published travel times as overrides and clear their `*_approx` flags. · serves DATA-FR-03, 12
- [x] **T13** Run the validator on base files and pairs. · Check: 0 errors apart from the expected "missing attractions/matrices" errors.

##### Attractions
- [x] **T14** Write `datatools/seed.py` (OpenTripMap, falling back to Overpass) and `datatools/draft.py`.
- [ ] **T15** Seed, draft and curate the priority cities JAI, DEL, GOA, BLR and VNS: 25–40 attractions each, every row checked against its source, `checked_on` filled. · serves DATA-FR-05, 08
- [ ] **T16** Validate the 5 priority cities. · Check: 0 errors for these cities.
- [ ] **T17** Seed, draft and curate AGR, HMP, MUN, RSH and DJL. · serves DATA-FR-05, 08
- [ ] **T18** Seed, draft and curate PDY, BOM, CCU, HYD and MAA. · serves DATA-FR-05, 08

##### Matrices
- [ ] **T19** Write `datatools/matrices.py` and build all 15 `matrices/<CITY>.json`. · serves DATA-FR-07
- [ ] **T20** Run the full validator. · Check: DATA-AT-01, 0 errors.

##### Database
- [ ] **T21** Write `datatools/sql/schema.sql` and create the `ref` schema in Neon.
- [ ] **T22** Write `datatools/load.py` (validate → one transaction → truncate → insert → version row). · serves DATA-FR-09, 11
- [ ] **T23** Write `datatools/report.py`: counts, tag coverage, approximation shares, `--db` comparison and `--sample`. · serves DATA-FR-12

##### Verify
- [ ] **T24** Load into Neon and run `report --db`. · Check: DATA-AT-03.
- [ ] **T25** Rollback test on a throwaway Neon branch. · Check: DATA-AT-04.
- [ ] **T26** Spot check 20 attractions, 10 hotels and all fare rows; record in `data/spot_check.md`. · Check: DATA-AT-05.
- [ ] **T27** Run `report`, then update the traceability section with every DATA-AT result. · Check: DATA-AT-06; 001 marked Done.

### Feature 002 — Optimization engine (single plan)

Status: Spec **Approved** · Plan *to be added* · Tasks *to be added*
Traces to: FR-010–FR-015, NFR-008, NFR-009 · Constitution Articles II and IX · Depends on: 001

#### 002 Spec

##### 1. Goal

Given a trip request, produce **one** feasible plan with the highest trip value, or a clear "no plan fits" answer with the minimum budget needed. The plan is checked by an independent validator before it is returned.

Variants (Saver / Balanced / Experience) and trade-offs are built on top of this engine in Feature 003.

##### 2. Scope

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

##### 3. Input — `TripRequest`

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

##### 4. Time model

All times are minutes after midnight, IST.

###### 4.1 Day windows

- **Daily window:** each day d = 1…D has a nominal window [S, S + H], where S = `day_start` (config, default 09:00) and H = `daily_hours_out` × 60. The window end is capped at `day_end_cap` (default 23:00).
- **Lunch:** a day whose window is at least 6 hours gets a 60-minute lunch break that must start between 12:30 and 14:30. It is modelled as a break in the routing time dimension.
- **Pace:** pace sets the activity limit per day and the share of the window that may be used.

| Pace | Max activities per day | Window fill |
|---|---|---|
| relaxed | 3 | 0.75 |
| balanced | 4 | 0.90 |
| packed | 6 | 1.00 |

###### 4.2 Journey time

For a transport option (mode m, class k), the door-to-door journey time is:

J = origin hub access + mode minutes + (90 if flight) + destination hub access

Hub access comes from `hubs.csv`; mode minutes come from `city_pairs.csv`.

**Options removed before solving:**

- modes the user avoids,
- modes not available for the pair,
- train or bus journeys with mode minutes > 1,200 (20 hours). These are too long for a 2–7 day trip.

If no option remains in either direction, the answer is `no_route` (section 8).

###### 4.3 First and last day

| Journey type | Rule |
|---|---|
| **Daytime** (flights; train/bus with mode minutes < 480) | **Outbound:** surface journeys leave the origin hub at 06:00 on day 1; flights depart at 07:00. Arrival at the destination centre = departure + mode minutes + destination access. Day 1 window starts at max(S, that arrival + 30). **Return:** must reach the origin hub by 23:00 on day D, so the latest departure from the destination centre = 23:00 − (mode minutes + destination access + 90 if flight). Day D window ends at min(window end, latest departure − 30). |
| **Overnight** (train/bus with 480 ≤ mode minutes ≤ 1,200) | **Outbound:** arrives at the destination hub at 07:00 on day 1. Day 1 window starts at max(S, 07:00 + destination access + 60). **Return:** leaves the destination hub at 21:00 on day D. Day D window ends at min(window end, 21:00 − destination access − 30). |

- A day whose window ends up shorter than 60 minutes has no activities.
- **Approximation:** the hotel stands in for the city centre when applying these rules (Constitution III.3).

###### 4.4 Usable time per day

U_d = (window length_d − lunch_d) × window fill

##### 5. Cost model

All amounts are integer rupees; P = people.

| Item | Formula |
|---|---|
| Outbound | P × fare(m, k, distance) + destination-side access cost × ⌈P ÷ capacity⌉ |
| Return | Same as outbound, in the other direction |
| Stay | (D − 1) nights × ⌈P ÷ 2⌉ rooms × hotel price per room per night |
| Food | P × D × food base(comfort) × city food multiplier |
| Entry fees | P × Σ entry fee of the chosen activities |
| Local travel | Σ over route legs of ride cost(km), using auto for `budget` comfort and cab for `mid`/`premium` (Feature 001 Spec §5.8) |
| **Total** | Sum of the above |
| **Contingency** | Budget − ⌊0.9 × budget⌋ (shown separately) |

- The fare formula is max(min_fare, base_fare + per_km × distance), using rail_km, road_km or air_km for the mode.
- Origin-side hub access is assumed to be paid by the traveller outside the trip budget, and is excluded. (Assumption, listed in section 13.)
- **Hard budget rule:** Total ≤ ⌊0.9 × budget_total⌋.

##### 6. Trip value

###### 6.1 Activity value

For activity a with tags t₁ (primary), t₂, t₃ and user weights w (0–5):

- match(a) = max over its tags of (w_tag ÷ 5) × (1.0 if the tag is primary, else 0.6)
- crowd(a) = 0.7 if `avoid_crowds` and crowd_level = high; 0.85 if `avoid_crowds` and crowd_level = medium; otherwise 1.0
- **v(a) = 100 × (rating ÷ 5) × (0.2 + 0.8 × match(a)) × crowd(a)**

An activity with match 0 keeps 20% of its rating value. This lets highly rated places fill spare time without outranking matched ones.

###### 6.2 Plan value

V = Σ v(a) over chosen activities
  + κ_t × (comfort_value(outbound) + comfort_value(return)) ÷ 2
  + β × (number of journeys using a preferred mode)
  − μ × (total minutes of local travel)

**Defaults:** κ_t = 15, β = 5, μ = 0.05 per minute. All of these are in the config file (NFR-009).

##### 7. Algorithm

###### 7.1 Pre-filter

Drop an attraction if any of the following is true:

- it is in `excludes`,
- it is closed on every trip day,
- its open interval cannot contain its visit inside any day's window.

A locked attraction that would be dropped makes the request infeasible, with the reason `lock_impossible` naming the attraction.

###### 7.2 Candidate hotels

All hotels of the user's comfort tier in the destination city (2–4 hotels).

###### 7.3 Stage 1 — selection (CP-SAT, one model per candidate hotel)

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

###### 7.4 Stage 2 — scheduling (OR-Tools routing)

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

###### 7.5 Feedback loop

If stage 2 drops a set S of activities:

1. Add the cut x_a = 0 for every a in S to stage 1. Keep the hotel and transport fixed.
2. Re-solve stage 1, then re-route.
3. Repeat until nothing is dropped, or `max_feedback_iters` (default 3) is reached.

The final plan is the last routed solution, which is feasible by construction.

###### 7.6 Exact costing and budget repair

Compute the exact local travel cost from the routed legs. If the exact total exceeds ⌊0.9 × budget⌋:

1. Remove the activity with the lowest v(a) ÷ (entry cost + its legs' cost).
2. Re-route.
3. Repeat until the plan fits the budget.

Locked activities are never removed. If they alone break the budget, the answer is infeasible with `lock_over_budget`.

###### 7.7 Validation

Run the validator (section 9) on the final plan. A validator failure is a bug: the engine returns error `internal_validation_failed` with the list of failed checks, and never returns the plan.

##### 8. Output

###### 8.1 Success — `Plan`

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

- `near_misses` here is a simple list: up to five unchosen activities with the highest v(a), each with a reason from {`budget`, `time`, `closed`}. Feature 003 refines how the reasons are computed.

###### 8.2 Not feasible

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

##### 9. Validator

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

The validator is a separate module with no imports from the solver code, so it can also check the baseline planners in Feature 008.

##### 10. Configuration — `backend/tripwise/config.yaml`

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

##### 11. Requirements

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

##### 12. Test trips — coverage rules

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

##### 13. Assumptions introduced by this spec

- **E-A1** Origin-side hub access cost is outside the trip budget, but its time counts.
- **E-A2** Daytime journeys leave at 06:00 (surface) or 07:00 (flights). Overnight journeys arrive at 07:00 and leave at 21:00.
- **E-A3** The hotel location stands in for the city centre for arrival and departure timing.
- **E-A4** Early hotel check-in is possible on day 1, and late checkout is not needed on day D, because the last night is D − 1.
- **E-A5** Local travel uses one mode per trip based on comfort tier (A-05).

##### 14. Acceptance tests

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

##### 15. Risks

- **Stage 1 estimates too optimistic:** if the 0.6 chain factor underestimates travel, stage 2 drops items often. Mitigation: log the drop rate in batch runs and tune `chain_factor` in config.
- **Routing time limit vs speed:** guided local search improves with time. Mitigation: measure value against time limit on the test trips and pick the knee point.
- **One-hotel-per-model loop:** 2–4 hotels × stage 1 is cheap, but variants in 003 may widen the candidate set. Mitigation: keep the stage 1 time limit low and reuse the model across hotels.

#### 002 Plan

*Added when Feature 001 tasks are under way.*

#### 002 Tasks

*Added with the plan.*

### Features 003–009

*Each is added here as its phase starts, using the same Spec / Plan / Tasks layout:*

| Feature | Name |
|---|---|
| 003 | Variants and trade-offs |
| 004 | Accounts and saved data |
| 005 | Trip planning API |
| 006 | Frontend |
| 007 | AI layer |
| 008 | Evaluation |
| 009 | Deployment |

---

## Part D — Traceability

Each product requirement maps to the feature spec that implements it, the tasks that build it and the tests that prove it.

Update this table when a feature's tasks are written (fill **Tasks**) and when its acceptance tests run (fill **Tests** and **Status**).

**Status values:** Planned · In progress · Pass · Fail

### Functional requirements

| Req | Summary | Feature spec | Feature reqs | Tasks | Tests | Status |
|---|---|---|---|---|---|---|
| FR-001 | Origin and destination from 15 cities, different | 005 | | | | Planned |
| FR-002 | Dates, 2–7 days, start tomorrow to +365 days | 005 | | | | Planned |
| FR-003 | Group size 1–6 | 005 | | | | Planned |
| FR-004 | Total or per-person budget, bounds | 005 | | | | Planned |
| FR-005 | Preferences (hours, interests, pace, comfort, modes, crowds) | 005 | | | | Planned |
| FR-006 | Free-text preferences parsed and confirmed | 007 | | | | Planned |
| FR-007 | Form pre-filled from saved profile | 005, 006 | | | | Planned |
| FR-010 | Complete plan produced | 002 | ENG-FR-02–05 | | ENG-AT-01 | Planned |
| FR-011 | Hard constraints respected | 002 | ENG-FR-01, 04, 07, 08 | | ENG-AT-01, 05 | Planned |
| FR-012 | Infeasible answer with minimum budget | 002 | ENG-FR-06 | | ENG-AT-07 | Planned |
| FR-013 | Prices labelled as estimates; breakdown sums exactly | 002, 006 | ENG-FR-02 | | ENG-AT-03 | Planned |
| FR-014 | Itinerary entries with times, fees and legs | 002 | ENG-FR-01, 05 | | ENG-AT-01, 02 | Planned |
| FR-015 | Contingency shown | 002, 006 | ENG-FR-02 | | ENG-AT-03 | Planned |
| FR-020 | Saver / Balanced / Experience variants | 003 | | | | Planned |
| FR-021 | Difference rule | 003 | | | | Planned |
| FR-022 | Side-by-side comparison | 006 | | | | Planned |
| FR-023 | Budget sensitivity ±10/20% | 003 | | | | Planned |
| FR-024 | Near-misses with reasons | 003 | | | | Planned |
| FR-025 | Trade-offs computed by the engine only | 003 | | | | Planned |
| FR-030 | Plan explanations grounded in plan data | 007 | | | | Planned |
| FR-031 | Chat mapped to fixed action set | 007 | | | | Planned |
| FR-032 | Chat actions re-solve and create versions | 007, 004 | | | | Planned |
| FR-033 | Unsupported requests handled | 007 | | | | Planned |
| FR-034 | "Why" answered from engine data | 007 | | | | Planned |
| FR-035 | Works without the LLM | 007 | | | | Planned |
| FR-040 | Sign up and log in | 004 | | | | Planned |
| FR-041 | Log out; 7-day sessions | 004 | | | | Planned |
| FR-042 | Preference profile | 004 | | | | Planned |
| FR-043 | Trips saved with all variants | 004 | | | | Planned |
| FR-044 | Plan versions and restore | 004 | | | | Planned |
| FR-045 | Chat history saved | 004 | | | | Planned |
| FR-046 | My Trips: rename, duplicate, delete | 004, 006 | | | | Planned |
| FR-047 | Per-user data isolation | 004 | | | | Planned |
| FR-050 | Seven pages | 006 | | | | Planned |
| FR-051 | Map with daily routes | 006 | | | | Planned |
| FR-052 | Budget chart and table | 006 | | | | Planned |
| FR-053 | Responsive from 360 px | 006 | | | | Planned |
| FR-060 | Curated data for 15 cities | 001 | DATA-FR-01–07 | | DATA-AT-01, 03 | Planned |
| FR-061 | Source and date on every record | 001 | DATA-FR-08 | | DATA-AT-01, 05 | Planned |
| FR-062 | Compilation month shown with prices | 001, 006 | DATA-FR-09 | | DATA-AT-03 | Planned |
| FR-070 | Evaluation vs greedy and LLM-only | 008 | | | | Planned |
| FR-071 | Chat intent test set | 008 | | | | Planned |

### Non-functional requirements

| Req | Summary | Feature spec | Feature reqs | Tasks | Tests | Status |
|---|---|---|---|---|---|---|
| NFR-001 | All variants ≤ 5 s p95 | 003, 009 | | | ENG-AT-08 (partial) | Planned |
| NFR-002 | Chat action ≤ 8 s p95 | 007, 009 | | | | Planned |
| NFR-003 | Security | 004, 009 | | | | Planned |
| NFR-004 | Free tiers only | 009 | | | | Planned |
| NFR-005 | LLM call limits | 007 | | | | Planned |
| NFR-006 | Browser support | 006 | | | | Planned |
| NFR-007 | Accessibility basics | 006 | | | | Planned |
| NFR-008 | Repeatable output | 002 | ENG-FR-10 | | ENG-AT-06 | Planned |
| NFR-009 | One config file | 002 | ENG-FR-09 | | ENG-AT-09 | Planned |
| NFR-010 | Validated dataset | 001 | DATA-FR-10 | | DATA-AT-01, 02 | Planned |

### Feature status

| Feature | Name | Spec | Plan | Tasks | Acceptance |
|---|---|---|---|---|---|
| B | Product | Approved | — | — | — |
| 001 | City data | Approved | Approved | Approved | — |
| 002 | Optimization engine | Approved | — | — | — |
| 003 | Variants and trade-offs | — | — | — | — |
| 004 | Accounts and saved data | — | — | — | — |
| 005 | Trip planning API | — | — | — | — |
| 006 | Frontend | — | — | — | — |
| 007 | AI layer | — | — | — | — |
| 008 | Evaluation | — | — | — | — |
| 009 | Deployment | — | — | — | — |

---

## Changelog

| Date | Section | Change | Reason |
|---|---|---|---|
| 2026-10-22 | A Constitution | Initial constitution | Phase 0 |
| 2026-10-22 | B Product | Initial draft | Phase 0 |
| 2026-10-22 | B Product | Approved | Review round |
| 2026-10-22 | C 001 Spec | Initial draft | Phase 0 |
| 2026-10-22 | C 001 Spec | Approved | Review round |
| 2026-10-22 | C 001 Spec | Attractions stored as one file per city (`attractions/<CITY>.csv`) | Easier to curate and review city by city |
| 2026-10-22 | C 001 Spec | Scripts live in package `datatools/`; commands are `python -m datatools.*` | Keep code separate from the `data/` folder (001 Plan §1) |
| 2026-10-22 | C 001 Spec | Added `*_minutes_approx` flags to city_pairs | DATA-FR-12 needs formula durations flagged |
| 2026-10-22 | C 001 Plan | Initial draft |  |
| 2026-10-22 | C 002 Spec | Initial draft | Phase 0 |
| 2026-10-22 | C 002 Spec | Approved | Review round |
| 2026-10-22 | A Constitution | v1.1: Articles I and X reworded for the single spec file | Follows the merge below |
| 2026-10-22 | All | Merged constitution, product spec, feature specs, plan, tasks and traceability into this single SPEC.md | User wants one spec file that grows phase by phase |
| 2026-10-22 | C 001 Plan, Tasks | Approved | Required before code by Article I.1 |
| 2026-10-22 | C 001 Plan §6, Tasks T05 | Broken fixtures are generated by the tests from one valid set; validator error codes listed | Matches the T05 implementation; avoids seven near-identical fixture folders |
| 2026-10-23 | C 001 Spec §5.4 | Sanity bounds: SL 0.2–1.0, 3A 0.5–2.2, 2A 0.8–3.2 per km; flight base_fare 1,000–6,000 | Real fare samples fit outside the old bounds (rail fares taper with distance) |
| 2026-10-23 | C 001 Spec §5.4, §7; Plan; T08 | Bus class NAC removed; buses are ACS only; 5 fare rows | No real non-AC seater fares could be sampled |
| 2026-10-23 | C 001 Spec §5.1 | food_multiplier band 0.6–2.2; a city with no cost-of-living source uses 1.0 as a marked approximation | Real metro/small-city meal prices fall outside 0.8–1.5; HMP and MUN have no source |
| 2026-10-23 | B §8, C 001 Spec §5.7 | Assumption A-08: premium food allowance = 2 × mid | No published premium figure exists |
| 2026-10-23 | C 001 Spec §5.8; Plan §3 | local_transport uses min_fare, min_km, per_km, approx; new ride-cost formula; state then median fallback for missing tariffs | Notified tariffs are minimum-fare-plus-per-km; many cities have none |
| 2026-10-23 | C 001 Spec §3, §5.1 | City centre is the hand-chosen tourist or commercial core, with the reason in source | Wikipedia reference points can sit outside the core (e.g. Mumbai) |
| 2026-10-23 | C 001 Spec §5.6, §7; Plan §4; T10; C 002 §7.2, §15 | 2–4 hotels per tier allowed when fewer can be found | Some cities have too few listed hotels in a band |
| 2026-10-23 | C 001 Spec §3; Plan §1 | checked_on = fetch date for values read from an opened page with evidence in data/raw/; empty only for TODO rows | Makes checked_on mechanical and auditable |
| 2026-10-23 | C 001 Spec §8; Plan §6; T26 | DATA-AT-05 spot check grows to 20 attractions, 10 hotels and all fare rows | Compensates for checked_on now being the fetch date |
| 2026-10-23 | C 001 Plan §1, §2.2 | Curation scripts live in datatools/curation/ and are committed | Derived values must be reproducible |
| 2026-10-23 | C 001 Spec §5.5 | rating = Wikipedia 12-month pageviews log-scaled 1–5 within each city; OpenTripMap rate 1/2/3 → 2/3/4 as fallback | One reproducible popularity measure for every city |
| 2026-10-23 | C 001 Spec §5.5 | crowd_level = rating terciles within each city | No public crowd data; popularity is the closest measurable proxy |
| 2026-10-23 | C 001 Spec §5.5 | Hours and fees from ASI or official sites first; otherwise default hours by place type and fee 0 for temple, viewpoint, market, beach | Official hours are not published for every attraction |
| 2026-10-23 | C 001 Spec §5.5 | visit_minutes defaults by place type (monument 90, museum 120, temple 45, viewpoint 30, market 90, beach 120, activity 180); other kinds map onto these seven | Visit durations are rarely published |
| 2026-10-23 | C 001 Spec §5.5; Plan §2.2 | New columns hours_approx and visit_approx | DATA-FR-12: approximations are flagged in the row |
| 2026-10-23 | C 001 Spec §5.5 | New column fee_approx: with no official fee, entry_fee is the median of ≥ 2 independent secondary sources (URLs in data/raw/attractions/fee_secondary.csv) and fee_approx = true; a fee the user read from an official booking page counts as official | Some official fees are not published without login; DATA-FR-12 needs the approximation flagged |
