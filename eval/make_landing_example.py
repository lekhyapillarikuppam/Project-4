"""The Landing page's example day, taken from a real engine plan so no number on the page is made up.

    python eval/make_landing_example.py      # writes frontend/src/pages/landing-example.json

Request: Delhi to Jaipur, 2 people, 3 days, balanced pace, mid comfort, history and culture first. The example is
day 2 of the engine's single plan: real stop times, entry fees for 2 (data/curated JAI fees) and ride costs and
minutes from the city matrix. backend/tests/test_landing_example.py fails if the file drifts from the engine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from tripwise import engine  # noqa: E402
from tripwise.models import Plan, TripRequest  # noqa: E402

OUT = ROOT / "frontend" / "src" / "pages" / "landing-example.json"
REQUEST = {"origin": "DEL", "destination": "JAI", "start_date": "2026-12-14", "end_date": "2026-12-16", "people": 2,
           "budget_total": 40000,
           "prefs": {"daily_hours_out": 9, "pace": "balanced", "comfort": "mid", "avoid_crowds": False, "modes": {},
                     "interests": {"nature": 1, "adventure": 0, "food": 2, "history": 5, "culture": 4, "spiritual": 1,
                                   "shopping": 1, "relaxation": 1, "nightlife": 0}},
           "locks": [], "excludes": []}
DAY = 2


def example() -> dict:
    p = engine.plan(TripRequest.model_validate(REQUEST))
    assert isinstance(p, Plan), p
    d = next(d for d in p.days if d.day == DAY)
    rows = []
    for i, s in enumerate(d.stops):
        leg = s.leg_from_prev
        rows.append({"leg": f"{leg.mode.capitalize()}{' from the hotel' if i == 0 else ''} · {leg.minutes} min", "cost": leg.cost})
        if d.lunch and s.start >= d.lunch[1] and (i == 0 or d.stops[i - 1].end <= d.lunch[0]):
            rows.append({"lunch": f"Lunch {d.lunch[0]}–{d.lunch[1]}"})
        rows.append({"time": f"{s.start}–{s.end}", "name": s.name, "fee": s.entry_cost})
    if d.return_leg:
        rows.append({"leg": f"{d.return_leg.mode.capitalize()} back to the hotel · {d.return_leg.minutes} min", "cost": d.return_leg.cost})
    if d.lunch and not any("lunch" in r for r in rows):
        rows.append({"lunch": f"Lunch {d.lunch[0]}–{d.lunch[1]}"})
    city = "Jaipur"
    return {"title": f"Day {DAY} · {city}", "people": REQUEST["people"], "rows": rows}


if __name__ == "__main__":
    OUT.write_text(json.dumps(example(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(OUT.read_text(encoding="utf-8"))
