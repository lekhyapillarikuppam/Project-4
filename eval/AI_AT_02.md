# AI-AT-02 — grounded explanations

Run 2026-10-26 with `python eval/run_explanations.py` (Groq `openai/gpt-oss-120b`, JSON mode, temperature 0.4,
reasoning effort low) on the first 10 feasible trips of `eval/test_trips.json`. Raw output: `eval/out/explanations.json`.

**Result: Pass.** All 10 trips grounded on the first or second try (target ≥ 9). 9 trips grounded on the first call;
in one earlier run T08's Saver text needed the second call. No template fallback was needed, and the final check
found 0 ungrounded names or ₹ amounts in the texts shown.

Grounding (`backend/api/ai/grounding.py`): every attraction or hotel name of the destination city found in the text
must be in that variant's plan or near-miss list; every ₹ amount must be a cost or budget figure of that plan.
Unit tests (`backend/tests/ai/test_grounding.py`) cover ungrounded names and amounts, the retry and the template.

Review: texts are 2–4 sentences (about 70–80 words), name a few highlights and quote the total; near-miss reasons
match the plan. Seen once: the Experience hotel described as "premium" when the plan's tier is mid. Tiers are not
part of the grounding check (Spec covers names and ₹ only), so this is noted, not fixed.
