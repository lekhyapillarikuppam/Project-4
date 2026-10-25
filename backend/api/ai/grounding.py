"""Grounding check for LLM text (AI-FR-02, AI-FR-03; FR-030).

Every attraction or hotel name of the trip's city found in the text must be in the plan or its near-miss list,
and every ₹ amount must be a cost or budget figure that appears in the plan (or in the extra numbers the caller
allows, such as a diff's Δcost). Names are matched case-insensitively, longest first, so "Qutb Minar Complex" is not also
counted as "Qutb Minar".
"""

from __future__ import annotations

import re
from typing import Iterable

from tripwise import data

_AMOUNT = re.compile(r"(?:₹|\bRs\.?|\bINR)\s?(\d[\d,]*(?:\.\d+)?)\s?(k\b|lakh\b)?", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def city_names(city: str) -> set[str]:
    ds = data.default()
    return ({a.name for a in ds.attractions.values() if a.city_id == city}
            | {h.name for h in ds.hotels.values() if h.city_id == city})


def plan_names(plan: dict) -> set[str]:
    names = {s["name"] for d in plan["days"] for s in d["stops"]} | {plan["hotel"]["name"]}
    return names | {m["name"] for m in plan.get("near_misses", [])}


MONEY_KEYS = {"cost", "entry_cost", "price_per_room_night", "outbound", "return", "stay", "food", "entry_fees",
              "local_travel", "total", "usable_budget", "contingency", "budget_total"}


def numbers(obj, key: str | None = None) -> set[int]:
    """Every rupee amount in a plan (values under money keys), rounded to whole rupees."""
    out: set[int] = set()
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        if key in MONEY_KEYS:
            out.add(int(round(obj)))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out |= numbers(v, k)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= numbers(v, key)
    return out


def names_in(text: str, known: Iterable[str]) -> set[str]:
    t = f" {_norm(text)} "
    found = set()
    for name in sorted(set(known), key=lambda n: -len(_norm(n))):
        n = _norm(name)
        if n and f" {n} " in t:
            found.add(name)
            t = t.replace(f" {n} ", " | ")
    return found


def amounts_in(text: str) -> list[int]:
    out = []
    for m in _AMOUNT.finditer(text):
        v = float(m.group(1).replace(",", ""))
        suffix = (m.group(2) or "").lower()
        v *= 1000 if suffix == "k" else 100000 if suffix == "lakh" else 1
        out.append(int(round(v)))
    return out


def problems(text: str, city: str, allowed_names: set[str], allowed_amounts: set[int]) -> list[str]:
    """Empty when the text is grounded; otherwise one line per ungrounded name or amount."""
    bad = [f"name not in the plan: {n}" for n in sorted(names_in(text, city_names(city) | allowed_names) - allowed_names)]
    bad += [f"amount not in the plan: ₹{a:,}" for a in amounts_in(text) if a not in allowed_amounts]
    return bad


def check_plan_text(text: str, plan: dict, city: str, extra_amounts: Iterable[int] = ()) -> list[str]:
    return problems(text, city, plan_names(plan), numbers(plan) | set(extra_amounts))
