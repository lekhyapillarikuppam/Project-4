# Tripwise — Product Specification

Spec 000 · Status: **Draft for review** · Created 2026-10-22
Course: UMC301 Applied Data Science and Artificial Intelligence · Project 4

---

## 1. Summary

Tripwise is a web app that plans a complete budget trip between two of 15 Indian cities. The user enters where and when they are going, how many people, the budget and their preferences. Tripwise returns two or three feasible plans. Each plan covers transport there and back, accommodation, local travel, a day-by-day itinerary, a budget breakdown and trade-offs. The user picks a plan and refines it through a chat assistant. Plans and history are saved to the user's account.

Tripwise has two layers:

- **Optimization engine:** chooses transport, accommodation and activities that respect the budget, trip duration, opening hours, travel times and daily time limits, while maximizing a defined trip value.
- **AI assistant (Groq LLM):** turns free-text preferences into structured weights, explains plans in plain language, and maps chat requests onto a fixed set of plan changes that the engine then carries out.

The guiding rule: the engine guarantees that every plan is feasible; the AI layer never edits a plan directly (Constitution, Article II).

## 2. Problem and motivation

Planning a budget trip means juggling fares, hotel prices, entry fees, opening hours, distances and personal interests at the same time. Spreadsheets don't handle the scheduling, and asking a general-purpose LLM produces plans that read well but often break the budget, visit places on days they are closed or pack days with impossible travel. Tripwise combines constrained optimization, which gives guarantees, with an LLM, which gives a natural interface.

## 3. Users

- **Primary:** students and young working people planning short domestic trips (2–7 days) alone or in small groups, often on a tight budget.
- **Secondary:** the course instructor and evaluators, who need to see clearly how the system works and why its plans are trustworthy.

## 4. Supported cities

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

## 5. User stories

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

## 6. Functional requirements

### 6.1 Trip inputs

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

### 6.2 Plan generation

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

### 6.3 Variants and trade-offs

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

### 6.4 AI assistant

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

### 6.5 Accounts and saved data

- **FR-040** Users sign up and log in with email and password.
- **FR-041** Users can log out. Sessions expire after 7 days.
- **FR-042** Users can save and edit a preference profile (the FR-005 fields).
- **FR-043** Each generated trip is saved with its inputs and all variants.
- **FR-044** The selected plan keeps a version history. The user can restore an earlier version, which becomes the newest version.
- **FR-045** The chat history is saved per trip.
- **FR-046** **My Trips** lists upcoming and past trips. The user can rename, duplicate (same inputs, editable before re-planning) and delete a trip. Delete asks for confirmation on the page.
- **FR-047** A user can never see or change another user's data.

### 6.6 Pages and interface

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

### 6.7 Data

- **FR-060** The app ships with curated data for the 15 cities: city access hubs, intercity distances and travel times, fare rates, attractions, hotels, food allowances, local transport rates and local travel times. Spec 001 defines it in full.
- **FR-061** Each curated record stores its source and the date it was checked.
- **FR-062** The app shows the dataset's compilation month next to prices ("Estimated prices, compiled Nov 2026").

### 6.8 Evaluation

- **FR-070** An evaluation harness runs Tripwise, a greedy baseline and an LLM-only baseline on a fixed set of 30 test trips. It checks all three with the same validator and reports constraint violations, trip value, budget use, share of time spent travelling and solve time.
- **FR-071** A test set of 50 hand-written chat requests, each with its expected actions, measures the assistant's intent accuracy.

## 7. Non-functional requirements

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

## 8. Assumptions

- **A-01** Prices are typical estimates for the compilation month. They are not live quotes, and seasonal price changes are not modelled in v1.
- **A-02** Hotel rooms hold two people, so rooms = ⌈group size ÷ 2⌉.
- **A-03** Entry fees use the Indian adult rate. Child and foreign-national rates are not modelled.
- **A-04** Each attraction has one opening interval per open day, and the same interval on every day it opens.
- **A-05** Local travel within a city is by auto-rickshaw (budget comfort) or cab (mid and premium comfort). Metro and city buses are not modelled in v1.
- **A-06** Times are Indian Standard Time, in 24-hour format.
- **A-07** Long journeys can be taken overnight. Spec 002 defines exactly how travel time reduces the first and last days.

## 9. Out of scope

- Real bookings, payments or live prices.
- Cities beyond the 15, and multi-city trips.
- A native mobile app.
- Seasonal or dynamic pricing, weather and festival calendars.
- Child or foreign-national pricing.
- Sharing trips with other users, or collaborative editing.
- Social login (Google, etc.). It may be added later through a spec amendment.
- Languages other than English.

## 10. Feature breakdown

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

## 11. Success criteria for the project

1. All acceptance tests in specs 001–009 pass and are recorded in `specs/traceability.md`.
2. On the 30 test trips, Tripwise plans have zero constraint violations. The results table also reports violation rates for the greedy and LLM-only baselines.
3. The deployed app completes a full trip (form → variants → refine in chat → saved in My Trips) for a new user.
4. At least three test users rate the plans' realism, and the ratings are recorded.

## 12. Glossary

| Term | Meaning |
|---|---|
| Plan | One complete trip proposal: transport, hotel, itinerary, local travel, food and budget |
| Variant | One of Saver, Balanced or Experience for the same request |
| Plan version | A saved state of the selected plan. Each chat change or restore creates one |
| Trip value | The engine's score of how well a plan matches the user, defined in spec 002 |
| Usable budget | 90% of the total budget. The remaining 10% is contingency |
| Daily hours out | Maximum hours per day the user spends outside the hotel |
| Access hub | The railway station, bus stand or airport used to reach a city |
| Near-miss | An activity that was a strong candidate but not chosen, with its reason |
| Cut | A constraint added to the selection stage when the scheduling stage cannot fit an activity |
| Validator | Independent code that checks any plan against all hard constraints |

## 13. Open questions

None blocking. Decisions deferred to feature specs:

- the exact Groq model (spec 007),
- the exact value-function weights, which are tuned during spec 002 and recorded in its config.

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-10-22 | Initial draft | Phase 0 |
