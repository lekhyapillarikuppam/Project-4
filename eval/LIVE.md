# Live checks (Feature 008, DEP-FR-03)

Deployed system, 2026-10-26:

- **Frontend:** https://tripwise-inky.vercel.app (Vercel, project `tripwise`, built with
  `VITE_API_URL=https://lekhya-audiobook.centralindia.cloudapp.azure.com/tripwise`).
- **API:** https://lekhya-audiobook.centralindia.cloudapp.azure.com/tripwise/ (Azure VM: 2 vCPU AMD EPYC 7763,
  836 MB RAM; systemd `tripwise-api` behind the Project 2 Caddy; Neon Postgres; Groq `openai/gpt-oss-120b`).

Each live run signs up one new `live-check-…@example.com` user on the production API.

## DEP-AT-01 — live full flow: Pass

`npx playwright test -c playwright.live.config.ts` (in `frontend/`; spec `tests-live/dep-at-01.spec.ts`, Chrome, no
local servers, real Groq). It signs up, plans Delhi to Jaipur (2 people, ₹50,000), chooses the first variant, sends
"Switch to a budget hotel" (the chat shows "Version 2 created" and the page moves to version 2), then opens My Trips
and finds the trip. Passed in 15 s. Screenshot: `frontend/test-shots/live-my-trips.png`. Re-run on the final deploy
(after the Groq key rotation and the last 007 changes): passed in 16.7 s; on the chat-deadline deploy: 14.9 s; on the limit_kind deploy: 38.1 s (passed; the test does not
time its steps).

## DEP-AT-02 — live timings: Pass (variants within NFR-001; chat within NFR-002 after the chat deadline)

`python eval/run_live.py` times each request from a laptop in India, so network, Caddy and the Neon write are
included. Raw rows: `eval/out/live.json`.

### Variants (NFR-001, p95 ≤ 5 s): Pass

| `POST /trips` (all variants) | p95 | Max |
|---|---|---|
| All 30 test trips (NFR-001) | 1.21 s | 1.54 s (T07) |
| T01–T10 (DEP-FR-03) | 1.54 s | 1.54 s (T07) |

All 30 returned 201, with 26 plans and the 4 infeasible trips (T25–T28) reported as infeasible.

**The VM is slower than the laptop.** Timed the same way on the laptop (`plan_variants` alone, one warm-up), the 30
trips give p95 0.68 s (T01–T10: 0.94 s), against 1.21 s (1.54 s) for the live request; every one of the 30 is slower
live, by 0.36 s on average. The VM has 2 vCPUs where the laptop has 8 cores (Ryzen 7 5800HS), and the live figure
also includes the round trip and the database write. Both are well within 5 s.

### Chat (NFR-002, p95 ≤ 8 s): Pass with the per-message deadline

`python eval/run_live.py --part chat`: one Delhi to Jaipur trip per run, Balanced, and the 10 AI-AT-04 messages in
sequence (1.5 s pause between messages, not timed), Groq Developer tier. With 10 messages a run, p95 is the
slowest message.

**With the chat deadline (AI-FR-03, deployed 2026-10-26: 7 s per message, call 1 at most 4 s, call 2 the rest
minus 0.5 s):**

| Run | p95 (= max of 10) | Next slowest | Median | Replies |
|---|---|---|---|---|
| 1 | 4.72 s | 4.11 s | 2.87 s | 10 new versions, 10 LLM replies |
| 2 | 7.41 s | 4.82 s | 2.81 s | 9 new versions (8 LLM replies, 1 template), 1 "assistant unavailable" |

Both runs are within 8 s. Run 2 shows both deadline paths, from the VM's log:

- "We love food, bump that up to 5" (7.41 s): call 1 took 0.6 s; call 2 timed out at its 4.5 s budget, so the
  template reply was used. The change was made (version 8).
- "Put Hawa Mahal on day 3" (4.82 s): call 1 timed out at 4.0 s, so the chat answered "assistant unavailable" and
  made no change; the traveller has to send it again.

Every other Groq call in both runs took 0.3–0.7 s.

**After the limit_kind chat fix** (deployed 2026-10-26 with dataset 1.1; call 1 now carries the `limit_kind`
schema, about 2,370 prompt tokens against about 1,850):

| Run | p95 (= max of 10) | Median | Replies |
|---|---|---|---|
| 1 | 7.30 s | 5.6 s | 10 answered: 7 LLM replies, 2 template, 1 "plan did not change" |
| 2 | 7.31 s | 4.6 s | 9 answered (7 LLM, 1 template, 1 "plan did not change"), 1 "assistant unavailable" |

Both runs are within 8 s, with less headroom than before. The VM's log shows 4 Groq read timeouts in the 20
messages: one on call 1 at 4.0 s ("Increase our budget to 60000" got "assistant unavailable") and three on call 2
at its remaining budget (template replies; the changes were made). Call 1's median was 450 ms and call 2's 922 ms.
"We love food, bump that up to 5" now gets the honest "Your plan did not change" reply: the higher food weight left
the plan the same.

**Before the deadline** (same day, Groq read timeout 10 s for both calls), for the record. Every message returned
201 with a new version:

| Run | p95 (= max of 10) | Next slowest | Median | Slow message |
|---|---|---|---|---|
| 1 | 12.20 s | 5.10 s | 2.88 s | "Make sure we visit Nahargarh Fort" |
| 2 | 13.01 s | 4.63 s | 3.72 s | "Put Hawa Mahal on day 3" |

18 of the 20 messages took 2.5–5.1 s. Each run had one message over 8 s, and in both the time went to Groq, as the
VM's log shows (`tripwise.ai` logs each call's duration):

- **Run 1:** call 1 (tools) took 0.5 s; call 2 (reply) hit Groq's read timeout at the configured 10 s
  (`groq.timeout_s`), so the reply fell back to the template, as AI-FR-03 specifies. The change itself was made.
- **Run 2:** call 1 took 3.6 s and call 2 took 5.9 s, against 0.3–1.6 s for every other call in the run.

Without the Groq time, each message takes about 2–3 s (re-planning on the VM, the Neon writes and the round trip),
so one slow Groq response put a whole run over 8 s. The deadline bounds that wait; the cost is that a slow Groq
response now gives a template reply or, if call 1 is slow, "assistant unavailable" (1 of 20 messages after the
change).

## DEP-AT-03 — security: Pass

| Check | Result |
|---|---|
| HTTPS only | `http://…/tripwise/health` → 308 to `https://…`; `http://tripwise-inky.vercel.app/` → 308 to HTTPS |
| CORS allows the app | Preflight from `https://tripwise-inky.vercel.app` → 200 with `Access-Control-Allow-Origin: https://tripwise-inky.vercel.app` |
| CORS rejects other origins | Preflight from `https://evil.example.com` → 400 with no `Access-Control-Allow-Origin`; a GET from that origin or from `http://localhost:5173` gets no `Access-Control-Allow-Origin` (`APP_ENV=production`) |
| API port not exposed | Port 8100 on 20.219.52.200 is closed from the internet (`Test-NetConnection`: false); only Caddy's Docker network reaches it (one UFW rule) |
| No secrets in the repo | `git grep` for Groq keys (`gsk_…`), Neon passwords (`npg_…`), Postgres URLs with a password, private keys, AWS keys and `JWT_SECRET=` values: no matches in the working tree or in any of the 91 commits (re-run 2026-10-26 with POSIX
character classes, checked against planted dummies first). No `.env`, `.env.local` or `.pem` file is tracked |
| Secrets on the VM | `/etc/tripwise.env`, owner root, mode 600, LF line endings, read by systemd only |
| Key rotation | 2026-10-26: the Groq key was rotated after the old one appeared in a local transcript (never in the repo); the old key is revoked, the VM and the local `.env` hold the new one (SHA-256 fingerprints match), and a live chat change succeeded with it |

Found and fixed during these checks:
1. **First request after a quiet spell returned 500.** Neon closes idle connections when its compute suspends, and
   the pool handed out a dead one (`SSL connection has been closed unexpectedly`). The pool now checks each connection
   on checkout and retires connections idle for 240 s (`db_pool.max_idle_s`); test `backend/tests/api/test_db_pool.py`.
2. `/etc/tripwise.env` had Windows line endings. systemd ignored them, but a shell sourcing the file would not, so
   they were removed.

## Left for the owner

- Friend test: 3 or more people rate the realism of their plans from 1 to 5. Record the ratings here.
- Safari, Firefox and mobile browsers (NFR-006) on the live site.
