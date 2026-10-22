# Tripwise Constitution

Version 1.0 · Ratified 2026-10-22

These are the project-wide rules. Every feature spec, plan, task and line of code must follow them. If a rule needs to change, amend this file first (see Governance).

---

## Article I — The spec is the source of truth

1. No code is written for a feature until that feature has an approved `spec.md`, `plan.md` and `tasks.md` in `specs/NNN-feature-name/`.
2. Code implements the spec. If code needs to behave differently from the spec, the spec is changed first, then the code.
3. A feature is **done** only when every acceptance test in its spec passes and the result is recorded in `specs/traceability.md`.

## Article II — The solver owns feasibility

1. Every plan shown to a user is produced by the optimization engine and has passed the independent plan validator.
2. The LLM never creates, edits or reorders a plan. It may only:
   - turn free text into structured preferences (a fixed JSON schema),
   - turn a chat message into one action from the fixed action set,
   - explain a plan using data the engine produced.
3. Every LLM output is schema-validated before use. Invalid output is rejected and never reaches the solver or the user as fact.
4. The app must still generate plans when the LLM is unavailable. Only explanations and chat are lost.

## Article III — Honest data

1. Every price shown is labelled as an estimate, with the month the estimate was compiled.
2. Every curated number (fare rate, entry fee, hotel price, opening hours) records its source and the date it was checked.
3. Approximations are documented where they are made (for example, rail distance approximated by road distance) and listed in the spec that introduces them.
4. Nothing is invented to fill a gap. Missing data is marked missing and fails validation until filled.

## Article IV — Testable requirements

1. Every requirement has an ID: `FR-xxx` / `NFR-xxx` in the product spec, and feature-scoped IDs (for example `DATA-FR-01`, `ENG-FR-01`) in feature specs.
2. Every feature requirement traces to at least one product requirement.
3. Every requirement has an acceptance criterion that a test or a recorded manual check can decide pass or fail. Words like "fast", "good" or "realistic" must come with a number or a procedure.

## Article V — Test before done

1. Each feature's acceptance tests are written from its spec before or alongside the implementation, never after the fact to match whatever the code does.
2. The engine and validator have automated tests. Pages and chat flows have at least a written manual test script with recorded results.
3. A failing acceptance test blocks the next feature in the build order.

## Article VI — Fixed stack

| Layer | Choice |
|---|---|
| Frontend | React (Vite), Leaflet with OpenStreetMap tiles, deployed on Vercel |
| Backend | Python 3.11+, FastAPI, Google OR-Tools (CP-SAT and routing), deployed on the Azure VM |
| Database | PostgreSQL on Neon |
| LLM | Groq API |
| Geo data | OpenStreetMap / OpenTripMap (attraction seeding), OpenRouteService (travel times) |

Adding a new external service or library with a large footprint requires a spec amendment that says why.

## Article VII — Scope discipline

1. Only the 15 cities in the product spec are supported.
2. Items in the product spec's **Out of scope** list are not built, even partially, unless the product spec is amended.
3. When in doubt, build the smaller version that satisfies the acceptance criteria.

## Article VIII — Security and privacy

1. Passwords are hashed with bcrypt. Plain-text passwords are never stored or logged.
2. A user can read and change only their own data. Every data endpoint checks ownership.
3. Secrets (API keys, database URL, JWT secret) live in environment variables, never in the repository. `.env.example` lists the names without values.
4. Only the data needed for the app is collected: email, password hash, preferences, trips and chat history.

## Article IX — Reproducibility

1. The same request on the same deployment and dataset version returns the same plans. Solver seeds and time limits are fixed in configuration.
2. Tunable weights and limits live in one configuration file, not scattered through code.
3. The evaluation can be re-run with one command and produces the same results table from the same inputs.

## Article X — Change control

1. Every spec change is committed with a message of the form `spec(NNN): <what changed> — <why>`.
2. Each spec ends with a **Changelog** section listing date, change and reason.
3. A change that affects another feature's spec updates that spec in the same commit.

---

## Governance

- This constitution takes precedence over every other spec.
- Amendments are made by editing this file, bumping the version (1.0 → 1.1 for clarifications, 2.0 for a changed rule), and adding a Changelog entry below.
- Before each feature is marked done, check its work against every Article.

## Changelog

| Date | Version | Change | Reason |
|---|---|---|---|
| 2026-10-22 | 1.0 | Initial constitution | Phase 0 |
