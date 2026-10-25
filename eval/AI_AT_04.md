# AI-AT-04 — chat changes end to end

Run 2026-10-26 with `python eval/run_chat_changes.py`: a DEL→JAI trip (3 days, 2 people, ₹50,000, Balanced) and
10 chat messages in sequence through `POST /trips/{id}/chat` (real Groq `openai/gpt-oss-120b`, API in-process on
schema `app_test`). Raw output: `eval/out/chat_changes.json`.

**Result: Pass, 10/10.** Every message created a new version that passes the validator, and the diff each reply was
written from equals the diff between the stored versions. Slowest message 4.8 s.

| # | Message | Tool(s) | Reply source |
|---|---|---|---|
| 1 | Make sure we visit Nahargarh Fort | lock_activity | LLM |
| 2 | Drop Jal Mahal please | exclude_activity | LLM |
| 3 | Increase our budget to 60000 | set_budget | LLM |
| 4 | We only want 6 hours out on day 2 | set_day_hours | LLM |
| 5 | Switch to a budget hotel | set_hotel_tier | LLM |
| 6 | Make the trip more relaxed | set_pace | LLM |
| 7 | We love food, bump that up to 5 | set_interest | LLM |
| 8 | Put Hawa Mahal on day 3 | move_activity | LLM |
| 9 | Come back by train in 3A | set_transport | LLM |
| 10 | Let's be out 10 hours every day | set_all_hours | template (LLM reply failed grounding) |

Found and fixed on the way:
1. **Engine:** after message 8, Balanced fell back to the Experience plan (mid hotel on a budget-comfort trip) but was
   labelled Balanced, so V-13 failed. Now `variant_at` keeps the label of the variant that produced the plan
   (regression test `test_fallback_plan_keeps_its_label`).
2. **Groq:** a 400 `tool_use_failed` (malformed tool call) is now retried once.
3. **Reply:** one reply called the plan total "your budget". Reply facts now include `budget_total`, and the prompt
   says which figure is which.

Stubbed tests (`backend/tests/api/test_api_chat.py`) cover every tool's change set, clarifying replies (ambiguous
or unknown names, day out of range), unsupported, "why" (near-miss, in plan, trial lock not saved), infeasible
changes and Groq unavailable.
