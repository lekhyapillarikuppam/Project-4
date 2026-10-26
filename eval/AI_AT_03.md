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

Median call 1.5 s; the slowest case took 26 s because of one Groq read timeout and retry.

Fixed on the way (the earlier partial run scored 43/50 = 86%):
1. **Name resolution:** a leading "the", "a" or "an" is dropped before matching, so "the temple" asks which temple
   (as "temple" did) instead of picking Garh Ganesh Temple on fuzzy score.
2. **Tool schema:** the `name` argument says to copy the traveller's words even when vague, and never to swap in a
   specific activity. This fixed C46 but not C47–C49.

Earlier fixes (tool descriptions for lock vs move and transport direction, nullable `explain.name`) are in the
Changelog.
