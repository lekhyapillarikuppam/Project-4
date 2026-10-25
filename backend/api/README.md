# Tripwise API (Feature 004)

FastAPI over the planning engine (`backend/tripwise`). It serves accounts, saved preference profiles, trips with
all their variants, plan versions, trade-offs and chat history. The dataset is read once from `data/curated/` at
start-up; user data lives in Postgres (Neon) in schema `app`.

## Run locally (PowerShell)

```powershell
cd C:\dev\Project4
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env        # then fill in the values
cd backend
.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
# check: curl http://localhost:8000/health
```

Start-up creates the schema named by `DB_SCHEMA` if it does not exist (`api/sql/app_schema.sql` is idempotent).
Interactive docs are at `http://localhost:8000/docs`.

## Environment variables

| Name | Required | Meaning |
|---|---|---|
| `DATABASE_URL` | yes | Neon Postgres connection string (pooled). Never committed |
| `JWT_SECRET` | yes | Long random string that signs login tokens (HS256, 7-day expiry) |
| `FRONTEND_ORIGIN` | yes in production | The web app's origin, the only origin CORS allows (for example the Vercel URL) |
| `APP_ENV` | no (default `development`) | `development` also allows `http://localhost:5173` through CORS; set `production` on the VM |
| `DB_SCHEMA` | no (default `app`) | Postgres schema for user data. The API tests use `app_test`, which they drop and recreate |
| `GROQ_API_KEY` | for Feature 007 | Groq API key for the AI features; planning works without it |

Tunables (solve concurrency, the 20 s wait before a 429, JWT lifetime, validation limits, DB pool size) are in
`backend/tripwise/config.yaml` under `api:`.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | – | Liveness and dataset version |
| GET | `/meta` | – | Dataset label, interests, paces, comforts, limits |
| GET | `/cities` | – | The 15 cities |
| POST | `/auth/signup`, `/auth/login` | – | `{email, password}` → `{token, user}` |
| GET | `/auth/me` | ✓ | Current user |
| GET, PUT | `/profile` | ✓ | Saved preferences (`{prefs}`) |
| POST | `/trips` | ✓ | Validate, plan all variants, save; body = trip form (`budget_total` or `budget_per_person`) |
| GET | `/trips?when=upcoming\|past` | ✓ | List |
| GET, PATCH, DELETE | `/trips/{id}` | ✓ | Get, rename (`{name}`), delete (with versions and chat) |
| POST | `/trips/{id}/duplicate` | ✓ | A copy of the request for the form; creates nothing |
| POST | `/trips/{id}/select` | ✓ | `{variant}` → the next plan version |
| POST | `/trips/{id}/replan` | ✓ | `{changes: {locks?, excludes?, budget_total?, prefs?}, source?, note?}` → next version, or 409 `infeasible` |
| GET | `/trips/{id}/versions`, `/trips/{id}/versions/{v}` | ✓ | Version list, one version |
| POST | `/trips/{id}/versions/{v}/restore` | ✓ | Copy version v as the newest |
| GET | `/trips/{id}/tradeoffs?variant=` | ✓ | Budget trade-offs (cached per request) |
| GET | `/trips/{id}/chat` | ✓ | Chat messages in order |

Auth is `Authorization: Bearer <token>`. Another user's ids return 404. Errors look like
`{"error": "<code>", "message": "<text>", "fields": {...}}`; a busy planner returns 429 after waiting 20 s.

## Tests

```powershell
cd C:\dev\Project4\backend
.venv\Scripts\python.exe -m pytest tests\api -q       # API-AT-01–08 against schema app_test
.venv\Scripts\python.exe -m pytest tests -q           # engine and API
```
