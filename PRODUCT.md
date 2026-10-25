# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary:** students and young working people in India planning short domestic trips (2–7 days), alone or in groups of up to 6, usually on a tight budget. Their job: turn "where, when, how many, how much, what we like" into a trip they can actually do, and refine it without starting over.
- **Secondary:** the course instructor and evaluators (UMC301 Project 4), who need to see how the system works and why its plans can be trusted.

## Product Purpose

Tripwise plans a complete budget trip between two of 15 Indian cities: transport there and back, one hotel, local travel, a day-by-day itinerary with times and a map, a budget breakdown, and what more or less money would change. It returns two or three distinct variants (Experience, Balanced, Saver); the user picks one and refines it through chat. Trips, versions and chat history are saved to the user's account.

Success: every plan shown is feasible, the user understands where the money goes, and changes are quick.

## Positioning

**Guaranteed-feasible plans.** An optimisation engine builds every plan, and an independent validator checks it against the budget, opening hours, closed days, travel times and daily time limits. The language model (Groq) parses free-text preferences, explains plans and turns chat requests into a fixed set of changes, but it never writes or edits a plan; the engine does (SPEC.md Constitution, Article II). A general-purpose chatbot can write a plan that reads well; Tripwise can show that its plan works.

## Operating Context

- Flow: sign up or log in → New trip form (or "Describe your trip" free text that fills the form) → compare 2–3 variant cards → choose one → plan detail (transport, hotel, map, day-by-day timeline, budget donut and table, budget trade-offs, near-misses, version history, chat assistant) → My Trips (upcoming and past, rename, duplicate, delete).
- Used on phones and laptops; tested at 360 px and 1280 px.
- Evaluators also read the repository: `SPEC.md`, `eval/RESULTS.md`, the acceptance-test records.

## Capabilities and Constraints

- 15 supported cities (JAI, AGR, HMP, MUN, RSH, DJL, GOA, PDY, DEL, BOM, BLR, CCU, HYD, VNS, MAA); 2–7 day trips; 1–6 people; budget ₹2,000 per person to ₹10,00,000 total.
- Preferences: daily hours out (4–14), nine interest weights (0–5), pace, stay comfort tier, transport-mode preferences, avoid crowds.
- All prices are estimates from a compiled dataset; every price shown carries an "estimated" marker, including ₹ amounts inside AI text.
- An infeasible request is answered with the minimum budget needed, not a broken plan.
- Planning works without the LLM; AI features degrade to notices or templates.
- Stack: React 18 + Vite + TypeScript + Tailwind frontend (Vercel); FastAPI + OR-Tools backend (Azure VM); Postgres (Neon); Groq `openai/gpt-oss-120b`.

## Brand Commitments

Only the name **Tripwise** is fixed. Voice, tone and logo are undecided.

## Evidence on Hand

- Curated dataset of attractions, hotels, fares and travel matrices for the 15 cities (`data/`), with an owner spot check (`data/spot_check.md`).
- Measured evaluation against greedy and LLM-only baselines (`eval/RESULTS.md`, `eval/charts/`).
- Acceptance-test records for the engine, API, UI and AI layer (`SPEC.md` Part D, `eval/AI_AT_*.md`, `frontend/TESTING.md`).
- No testimonials, user numbers, ratings or press exist. Do not invent them. A friend test (3+ people rating realism) is planned but not done.

## Product Principles

1. Feasibility is the promise: never show a plan the engine and validator have not approved.
2. Show the working: costs, times and reasons stay visible so users and evaluators can check the claim.
3. Honest numbers: prices are estimates and say so; AI text may only cite names and amounts that are in the plan.
4. Refine, don't restart: every change makes a new version that can be undone.
5. AI is an interface, not the planner: if the LLM is down, the product still plans.

## Accessibility & Inclusion

WCAG 2 AA (NFR-007): keyboard-only operation with visible focus, axe-core scans with zero violations, map markers with text labels and colour-blind-safe day colours, layouts working at 360 px.
