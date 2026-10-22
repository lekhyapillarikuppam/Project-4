# Tripwise

AI-powered budget trip planner for 15 Indian cities. Course project 4 for UMC301 Applied Data Science and Artificial Intelligence, built with spec-driven development (SDD).

Give Tripwise an origin, a destination, dates, a group size, a budget and your preferences. It returns two or three feasible trip plans covering transport there and back, a hotel, a day-by-day itinerary, local travel and a full budget breakdown with trade-offs. You can then refine your chosen plan in chat.

- **Optimization engine** (OR-Tools): guarantees every plan respects the budget, opening hours, travel times and daily limits.
- **AI assistant** (Groq): understands preferences, explains plans and turns chat requests into plan changes. It never edits a plan directly.

> Status: Feature 001 (city data) planned. No application code yet.

## Repository layout

```
Project4/
├── SPEC.md                    ← the single spec: rules, product, features, traceability
├── CLAUDE.md                  instructions for Claude Code
├── datatools/                 data scripts (Feature 001)
├── backend/                   FastAPI + OR-Tools (Feature 002)
├── frontend/                  React (Vite) (Feature 006)
├── data/
│   ├── raw/                   seed downloads and API caches (not edited by hand)
│   └── curated/               the dataset (Feature 001)
└── eval/                      test trips and evaluation (Features 002, 008)
```

## How we work (SDD)

Everything is specified in one file, `SPEC.md`, which grows phase by phase. Each feature goes through the same cycle, in build order 001 → 009:

1. **Specify:** add the feature's **Spec** subsection to Part C, covering what and why, requirements with IDs and acceptance tests. Review it once.
2. **Plan:** add its **Plan** subsection, covering how: design, modules, data model, interfaces.
3. **Tasks:** add its **Tasks** subsection: small, ordered, checkable tasks, each naming the requirement IDs it serves.
4. **Implement:** work through the tasks in order.
5. **Verify:** run the acceptance tests and record the results in Part D (Traceability).

If the code needs to differ from the spec, change `SPEC.md` first, add a Changelog row, and commit it with the reason (`spec(<section>): … — …`).

## Stack

React (Vite) + Leaflet on Vercel · Python FastAPI + OR-Tools on an Azure VM · PostgreSQL on Neon · Groq LLM · OpenTripMap, OpenStreetMap and OpenRouteService for geo data.

## Setup

Copy `.env.example` to `.env` and fill in the values. Setup steps for the backend and frontend will be added by Features 002, 005 and 006.

## Notice

All prices in Tripwise are estimates compiled from public sources. They are not live quotes, and nothing in the app can be booked.
