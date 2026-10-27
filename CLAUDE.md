# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Instructions for Claude Code — Tripwise

This project uses spec-driven development. Everything is in one file, `SPEC.md`. Before doing anything, read:

1. **Part A — Constitution:** the rules. They override everything else.
2. **Part B — Product.**
3. The **Part C** feature you are working on: its Spec, Plan and Tasks subsections.

`specs/` is the pre-merge Phase 0 layout and is stale (its constitution still points at `specs/NNN-*/`). `SPEC.md`
is the only spec. Features 001–008 are all done (Part D, "Feature status"). New work comes in as owner follow-ups
(F1, F2, … F11 so far). Each one changes the spec first (a `spec(...)` commit and a Changelog row), then the code,
then the tests, with results recorded in Part D.

## Rules

- Work only on tasks listed in the current feature's Tasks subsection, in order. Do not start the next feature.
- Do not add features, endpoints, fields or dependencies that the spec does not ask for. If something seems missing, stop and say so instead of improvising.
- Do not edit `SPEC.md` except to tick finished tasks, unless asked. If the code cannot match the spec, stop and explain the conflict.
- Every task you finish: tick it in `SPEC.md` (`- [x]`), and mention the requirement IDs it served in the commit message.
- Write the acceptance tests named in the spec. A task is not finished until its tests pass.
- All tunable numbers go in `backend/tripwise/config.yaml`, never hard-coded.
- The LLM (Groq) must never produce or edit a plan; only the engine does (Constitution II).
- Never commit secrets. Read them from environment variables; add new names to `.env.example`.

## Environment

- Windows, VS Code, PowerShell (not WSL). Give commands in PowerShell syntax.
- Python 3.11+ in a virtual environment at `backend/.venv`.
- The repository root is `C:\dev\Project4`.

## Commands

Backend (run from `backend\`; `backend/conftest.py` puts `backend/` on the import path):

```powershell
.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000     # API; docs at /docs
.venv\Scripts\python.exe -m pytest -q                                     # all backend tests
.venv\Scripts\python.exe -m pytest -q -m "not slow"                       # skip the batch tests over eval/test_trips.json
.venv\Scripts\python.exe -m pytest tests/test_solver.py::test_name -q     # a single test
.venv\Scripts\python.exe -m tripwise.cli plan ..\eval\example_request.json   # also: variants, tradeoffs, batch
```

The API tests (`tests/api/`) use the real Neon database from `.env`, in schema `app_test`, which they drop and
recreate. They skip when `DATABASE_URL` or `JWT_SECRET` is missing. AI tests use a Groq stub.

Frontend (run from `frontend\`):

```powershell
npm run dev                  # Vite on :5173
npm run build                # tsc --noEmit + vite build
npx playwright test          # starts uvicorn (DB_SCHEMA=app_e2e_test, GROQ_API_KEY="") and Vite; runs at 1280 and 360 px
npx playwright test tests/f11-empty-fields.spec.ts --project=chromium-1280   # a single spec, one viewport
$env:E2E_LIVE_GROQ="1"; npx playwright test tests/ai-live-chat.spec.ts       # opt-in, real Groq
npx playwright test -c playwright.live.config.ts                             # DEP-AT-01 against the deployed site
```

Data and eval (from the repo root): `python -m datatools.<module>` rebuilds and validates `data/curated/`
(Feature 001). `python eval/run_eval.py` runs the evaluation (results go in `eval/RESULTS.md`).

Deploy: run `.\deploy\deploy.ps1` for the backend (it ships `git archive HEAD`, so commit first). Deploy the frontend
with the Vercel CLI from `frontend\`; README.md "Deploy" has the exact command.

## Architecture

- **`backend/tripwise/`: the planning engine.** `engine.plan()` runs prefilter → hotel loop with `stage1` (CP-SAT
  selection) → `stage2` (routing each day under opening hours and travel times) → feedback cuts → exact costing
  (`costs`) and budget repair → fill step → validator gate. `variants.py` reruns it with other objectives and hotel
  tiers to get Saver/Balanced/Experience, and `tradeoffs.py` computes the trade-off figures. `data.py` loads
  `data/curated/` into memory once. `config.py` reads `config.yaml`, which holds every tunable, the API ones included
  (under `api:`).
- **`backend/validator/`: an independent check (V-01…V-16)** that every plan passes before anyone sees it.
  It must not reuse engine logic. The eval also runs baseline and LLM-only plans through it.
- **`backend/api/`: FastAPI (Feature 004).** It has routers per resource. `solver.py` runs engine calls in a bounded
  thread pool and returns 429 when no slot frees up in time. `db.py` is a psycopg pool on Neon, schema from
  `DB_SCHEMA`, and `sql/app_schema.sql` is applied at startup (idempotent). Plans are stored as numbered versions per
  trip; select, replan, restore and chat each create a new version.
- **`backend/api/ai/`: the Groq layer (Feature 007).** `parse` turns free text into preferences, `explain` explains
  a plan, and `chat` makes at most 2 Groq calls: one picks tools, which the API turns into a replan request for the
  engine, and one writes a reply from `diff` between versions. `grounding` checks every name and ₹ amount in an AI
  reply against the plan, and falls back to a template if any fails. Everything AI-related must degrade gracefully
  when `GROQ_API_KEY` is empty.
- **`frontend/`: React 18, Vite, TS, Tailwind, TanStack Query, react-leaflet.** `src/api` is the client
  (`VITE_API_URL`), and `src/pages` holds the 7 pages. Every ₹ amount shown must be marked as an estimate (UI-AT-09).
  Pages must work at 360 px with no horizontal scroll and pass axe. UI tests are pinned to the en-IN locale.
  `PRODUCT.md` and `.impeccable/` hold the design context for the Impeccable skill/hooks.
- **Production:** the backend runs on an Azure VM (systemd `tripwise-api`, Caddy at `/tripwise/*`, 1 uvicorn worker,
  secrets in `/etc/tripwise.env`), and the frontend is on Vercel.

## Commit messages

- `feat(NNN): <task> [FR/ENG/DATA ids]`
- `test(NNN): <what> [ids]`
- `spec(<section>): <change> — <reason>`
- `chore: <what>`

Follow-ups put the F number in the scope, for example `feat(006 F11): ... [UI-FR-02]`.
