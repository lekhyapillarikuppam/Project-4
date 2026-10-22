# Tripwise

AI-powered budget trip planner for 15 Indian cities. Course project 4 for UMC301 Applied Data Science and Artificial Intelligence, built with spec-driven development (SDD).

Give Tripwise an origin, a destination, dates, a group size, a budget and your preferences. It returns two or three feasible trip plans covering transport there and back, a hotel, a day-by-day itinerary, local travel and a full budget breakdown with trade-offs. You can then refine your chosen plan in chat.

- **Optimization engine** (OR-Tools): guarantees every plan respects the budget, opening hours, travel times and daily limits.
- **AI assistant** (Groq): understands preferences, explains plans and turns chat requests into plan changes. It never edits a plan directly.

> Status: Phase 0 — specs in progress. No application code yet.

## Repository layout

```
Project4/
├── specs/                     ← source of truth (read these first)
│   ├── constitution.md        project-wide rules
│   ├── traceability.md        requirement → spec → task → test → status
│   ├── _templates/            templates for spec.md, plan.md, tasks.md
│   ├── 000-product/spec.md    top-level product spec
│   ├── 001-city-data/         curated dataset
│   └── 002-optimization-engine/
├── backend/                   FastAPI + OR-Tools (from spec 002)
├── frontend/                  React (Vite) (from spec 006)
├── data/
│   ├── raw/                   seed downloads and API caches (not edited by hand)
│   └── curated/               the dataset (from spec 001)
└── eval/                      test trips and evaluation (specs 002, 008)
```

## How we work (SDD)

Each feature goes through the same cycle, in build order 001 → 009:

1. **Specify:** write `specs/NNN-name/spec.md`, covering what and why, requirements with IDs and acceptance tests. Review it once.
2. **Plan:** write `plan.md`, covering how: design, modules, data model, interfaces.
3. **Tasks:** write `tasks.md`: small, ordered, checkable tasks, each naming the requirement IDs it serves.
4. **Implement:** work through `tasks.md` in order.
5. **Verify:** run the spec's acceptance tests and record the results in `specs/traceability.md`.

If the code needs to differ from the spec, change the spec first and commit it with the reason (`spec(NNN): … — …`).

## Stack

React (Vite) + Leaflet on Vercel · Python FastAPI + OR-Tools on an Azure VM · PostgreSQL on Neon · Groq LLM · OpenTripMap, OpenStreetMap and OpenRouteService for geo data.

## Setup

Copy `.env.example` to `.env` and fill in the values. Setup steps for the backend and frontend will be added by specs 002, 005 and 006.

## Notice

All prices in Tripwise are estimates compiled from public sources. They are not live quotes, and nothing in the app can be booked.
