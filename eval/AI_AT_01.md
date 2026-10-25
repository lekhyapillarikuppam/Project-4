# AI-AT-01 — free-text preference parsing

Run 2026-10-26 with `python eval/run_parse_samples.py` (Groq `openai/gpt-oss-120b`, JSON mode, temperature 0.2).
Samples: `eval/parse_samples.json`; raw outputs: `eval/out/parse_samples.json`.

**Result: Pass.** 10 of 10 returned valid prefs (schema-validated). Weights judged sensible by manual review on 10 of 10 (target ≥ 9).

| ID | Text (short) | Parsed (key points) | Review |
|---|---|---|---|
| P01 | BLR→Goa, 2, 40k, beaches, seafood, nightlife, no temples, hate long buses | food 5, nightlife 5, relaxation 4, nature 4, spiritual 0; bus avoid, flight preferred; BLR→GOA, 2 people, ₹40,000 | Sensible |
| P02 | Solo history buff, every fort in Jaipur, packed | history 5, culture 2, others 0; packed, 12 h; JAI, 1 person | Sensible |
| P03 | Family of four, kids, relaxed, parks and zoo, mid-range | nature 4, relaxation 3; relaxed, mid; 4 people | Sensible |
| P04 | Rishikesh retreat, yoga, aarti, one rafting trip, avoid crowds | spiritual 5, nature 3, adventure 2; relaxed; avoid crowds; RSH | Sensible |
| P05 | Hyderabad foodies, 3 people, ₹15,000 each | food 5, others 0; budget comfort; HYD, 3 people, ₹15,000 per person | Sensible (budget comfort inferred from the budget) |
| P06 | Premium, galleries, museums, restaurants in Mumbai, hates flying | culture 5, food 4, history 2; premium; flight avoid; BOM | Sensible |
| P07 | Backpacker, hostels, trains only, trekking, waterfalls, Munnar | nature 5, adventure 5; budget; train preferred, flight avoid; MUN | Sensible (bus left neutral although "trains only") |
| P08 | Relax: beach, cafes, a little shopping, 5 h days | relaxation 5, shopping 3, food 2; relaxed; 5 h | Sensible (avoid crowds turned on, not asked for) |
| P09 | Kolkata culture, colonial buildings, book street, sweets, couple | culture 5, food 4, history 3; CCU, 2 people | Sensible |
| P10 | Party trip, 6 friends, clubs and bars, long days | nightlife 5, others 0; packed, 12 h; 6 people | Sensible |

Notes: the first run hit Groq's free-tier tokens-per-minute limit (HTTP 429) on two samples and named no destination when only one
city was mentioned. The client now retries once when Groq asks for a wait of ≤ 5 s, the script spaces its calls by 4 s, and the
prompt says a single named city is the destination. Reviewed by Claude Code (the owner may re-review the raw outputs).
