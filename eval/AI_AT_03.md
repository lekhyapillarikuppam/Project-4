# AI-AT-03 — chat tool accuracy

Run 2026-10-26 with `python eval/run_chat_intents.py` (fresh, all 50 cases in one run on the final code): the 50
hand-written messages in `eval/chat_intents.json` against a DEL→JAI trip (3 days, 2 people, ₹50,000, Balanced),
each through chat call 1 only (real Groq `openai/gpt-oss-120b`, the real system prompt, tools and trip context; no
replan). A message is correct when the model calls exactly the expected tool with the expected arguments, names
compared after the server's name resolution; for the 5 ambiguous messages, when the server ends with a clarifying
question. Raw output: `eval/out/chat_intents.json`.

**Result: Pass, 45/50 = 90%** (threshold ≥ 90%, FR-071). The margin is zero: one more miss would fail.

| Expected | Correct |
|---|---|
| lock_activity | 5/5 |
| exclude_activity | 4/4 |
| set_budget | 4/4 |
| set_day_hours | 3/3 |
| set_all_hours | 3/3 |
| set_hotel_tier | 3/3 |
| set_transport | 3/4 |
| set_pace | 3/3 |
| set_interest | 3/3 |
| move_activity | 3/3 |
| regenerate | 2/2 |
| explain | 3/3 |
| unsupported | 4/5 |
| ambiguous (clarifying question) | 2/5 |

Misses:

| Case | Message | Expected | Got |
|---|---|---|---|
| C25 | Take the bus there | set_transport, direction out | direction both |
| C45 | Do we need a visa? | unsupported | explain |
| C47 | Skip the garden | clarifying question | exclude_activity "Sisodia Rani Garden" |
| C48 | Make sure we see the fort | clarifying question | lock_activity "Nahargarh Fort" |
| C49 | Remove the mandir | clarifying question | exclude_activity "Birla Mandir" |

The three ambiguous misses are the model choosing an activity itself instead of passing on the traveller's words,
so the server never sees the vague name. The plan stays engine-made and valid either way, and the reply names the
activity that was changed, so the traveller can undo it.

Not tuned further to avoid overfitting the test set; known weakness: vague names.

## Re-run with `limit_kind` (2026-10-26): Fail on the mean of 3 runs

Since 2026-10-26 AI-AT-03 is scored on the mean of 3 fresh runs. Before shipping the chat fix for the owner's bug
report (`limit_kind`, list-valued exclude/lock, no other-activities context), both versions were run 3 times at
the same time, with no edits between runs:

| Code | Run 1 | Run 2 | Run 3 | Mean |
|---|---|---|---|---|
| Deployed before the fix (`81bd9a3`) | 45 | 45 | 44 | 44.7 / 50 (89.3%) |
| With the fix (shipped) | 43 | 43 | 42 | **42.7 / 50 (85.3%)** |

Failed cases per run:
- Before: C25, C45, C47, C49, C50 (run 3 also C48).
- With the fix: C18, C23, C25, C45, C46, C47, C48 (run 3 also C49).

The runs are not noisy: each version fails nearly the same cases every time (±1). The difference is systematic.
The fix loses C18 ("Make each day 7 hours" → `set_day_hours`), C23 ("Fly both ways" → train) and C46 ("Add the
temple" → a specific temple, no clarifying question), and gains C50 and usually C49. It was shipped under the
owner's rule fixed before the runs (ship if the new mean is within 2 cases of the old; here exactly 2.0), because it
fixes a real user bug: the chat regression set built from the owner's failures went from 0/6 to 6/6 runs meeting
the request (`eval/chat_regression.json`). No prompt was changed after the runs.

Median call 1.5 s; the slowest case took 26 s because of one Groq read timeout and retry.

Fixed on the way (the earlier partial run scored 43/50 = 86%):
1. **Name resolution:** a leading "the", "a" or "an" is dropped before matching, so "the temple" asks which temple
   (as "temple" did) instead of picking Garh Ganesh Temple on fuzzy score.
2. **Tool schema:** the `name` argument says to copy the traveller's words even when vague, and never to swap in a
   specific activity. This fixed C46 but not C47–C49.

Earlier fixes (tool descriptions for lock vs move and transport direction, nullable `explain.name`) are in the
Changelog.
