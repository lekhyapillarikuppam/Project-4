# Traceability

Each product requirement maps to the feature spec that implements it, the tasks that build it and the tests that prove it.

Update this table when a feature's tasks are written (fill **Tasks**) and when its acceptance tests run (fill **Tests** and **Status**).

**Status values:** Planned · In progress · Pass · Fail

## Functional requirements

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

## Non-functional requirements

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

## Feature status

| Spec | Feature | spec.md | plan.md | tasks.md | Acceptance |
|---|---|---|---|---|---|
| 000 | Product | Draft | — | — | — |
| 001 | City data | Draft | — | — | — |
| 002 | Optimization engine | Draft | — | — | — |
| 003 | Variants and trade-offs | — | — | — | — |
| 004 | Accounts and saved data | — | — | — | — |
| 005 | Trip planning API | — | — | — | — |
| 006 | Frontend | — | — | — | — |
| 007 | AI layer | — | — | — | — |
| 008 | Evaluation | — | — | — | — |
| 009 | Deployment | — | — | — | — |
