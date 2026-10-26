# Frontend acceptance tests (006 UI-AT-01–09)

Run on 2026-10-25 on the developer laptop (Windows 11, Node 24.21.0, Chromium via Playwright 1.64.0) against a
local API (`uvicorn api.main:app`, schema `app_e2e_test`) and the Vite dev server. Playwright starts both.

```powershell
cd C:\dev\Project4\frontend
npm install
npx playwright install chromium
npx playwright test            # 15 tests (1 live test skipped), about 70 s
```

| ID | Test file | Result | Notes |
|---|---|---|---|
| UI-AT-01 | `tests/ui-at-01-03-plan.spec.ts` | Pass | Sign up → New trip (Delhi → Agra) → 3 variant cards in 888 ms (limit 8 s) |
| UI-AT-02 | `tests/ui-at-02-06-detail.spec.ts` | Pass | Transport, hotel, all 4 days, map with one colour per day route, hotel and numbered stop markers; budget lines sum to the total, total + contingency + unused = budget |
| UI-AT-03 | `tests/ui-at-01-03-plan.spec.ts` | Pass | ₹4,000 Bengaluru → Delhi shows the minimum budget; Edit budget returns to the form with every value kept |
| UI-AT-04 | `tests/ui-at-04-form.spec.ts` | Pass | Same city, start today, 9-day trip, 7 people, ₹3,000 for 2, every mode avoided, all interests 0 — each blocked before any request; a forced server 422 shows next to its field |
| UI-AT-05 | `tests/ui-at-05-mytrips.spec.ts` | Pass | Upcoming / Past tabs (past trip inserted by `tests/make_past_trip.py`), inline rename, duplicate pre-fills the form, delete asks first (Escape cancels) |
| UI-AT-06 | `tests/ui-at-02-06-detail.spec.ts` | Pass | Trade-offs panel loads (figures or "limited by time"); restoring version 1 creates version 3 |
| UI-AT-07 | `tests/ui-at-07-responsive.spec.ts` | Pass | All 7 pages at 360 px and 1280 px: no horizontal scroll, no element past the right edge; screenshots in `test-shots/` |
| UI-AT-08 | `tests/ui-at-08-09-a11y.spec.ts` | Pass | Sign up, plan and choose with the keyboard only; a visible focus ring at every Tab stop |
| UI-AT-09 | `tests/ui-at-08-09-a11y.spec.ts` | Pass | Every ₹ amount on the comparison and detail pages (including trade-offs) sits under an Estimated marker or is the user's own budget; footer shows "Estimated prices, compiled Nov 2026" |
| UI-FR-09 | `tests/ui-at-08-09-a11y.spec.ts` | Pass | A 429 shows "The planner is busy right now" with Retry |
| NFR-007 | `tests/ui-at-08-09-a11y.spec.ts` | Pass | axe-core WCAG 2 A/AA scan of all 7 pages: 0 violations (map tiles excluded) |

Screenshots (`test-shots/`): `1-landing`, `2-login`, `3-new-trip`, `4-comparison`, `5-plan-detail`, `6-my-trips`,
`7-profile`, each at `-360.png` and `-1280.png`. They were also reviewed by eye.

Not covered automatically: Safari, Firefox and mobile browsers (NFR-006). These are checked on the deployed site in Feature 008.

## Feature 007 additions (2026-10-26)

The API runs with an empty `GROQ_API_KEY` in these tests, so the AI parts show their fallbacks and no test calls Groq.

| Check | Test file | Result | Notes |
|---|---|---|---|
| Chat panel, no Groq (AI-AT-05, UI side) | `tests/ai-ui-chat.spec.ts` | Pass | At 360 px (bottom sheet, opened by "Ask the assistant") and 1280 px (docked): the message and an "assistant is unavailable" reply appear, no version is created, history survives a reload; explanations show their notice; the Describe-your-trip box is on New trip |
| Live chat, version chip and undo | `tests/ai-live-chat.spec.ts` | Pass (live, 2026-10-26) | Opt-in, real Groq: `$env:E2E_LIVE_GROQ="1"; npx playwright test tests/ai-live-chat.spec.ts`. "Switch to a budget hotel" → "Version 2 created", the page moves to version 2; Undo restores version 1 as version 3; screenshot `test-shots/8-chat-1280.png` |

₹ amounts inside AI text (explanations, chat replies) are rendered with the "est." tag, as UI-AT-09 requires.

## Feature 008 live check (2026-10-26)

| Check | Test file | Result | Notes |
|---|---|---|---|
| Live full flow (DEP-AT-01) | `tests-live/dep-at-01.spec.ts` | Pass (15 s) | Runs against https://tripwise-inky.vercel.app and the VM API with real Groq, no local servers: `npx playwright test -c playwright.live.config.ts` (`LIVE_URL` overrides the site). Sign up, plan Delhi to Jaipur, choose, "Switch to a budget hotel" gives version 2, My Trips lists the trip. Each run adds one `live-check-…@example.com` user |
