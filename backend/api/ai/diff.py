"""Difference between two plan versions (AI-FR-03): activities added, removed and moved, hotel and transport
changes, Δcost and Δvalue. The chat reply is written from this, and AI-AT-04 checks it against the versions."""

from __future__ import annotations


def _days(plan: dict) -> dict[str, tuple[int, str]]:
    return {s["attraction_id"]: (d["day"], s["name"]) for d in plan["days"] for s in d["stops"]}


def _journey(j: dict) -> str:
    return f"{j['mode']} {j['class']}"


def diff(old: dict, new: dict) -> dict:
    a, b = _days(old), _days(new)
    out = {
        "added": [b[i][1] for i in b if i not in a],
        "removed": [a[i][1] for i in a if i not in b],
        "moved": [{"name": b[i][1], "from_day": a[i][0], "to_day": b[i][0]} for i in b if i in a and a[i][0] != b[i][0]],
        "hotel": None, "transport": {},
        "delta_cost": new["budget"]["total"] - old["budget"]["total"],
        "delta_value": round(new["value"] - old["value"], 2),
        "old_total": old["budget"]["total"], "new_total": new["budget"]["total"],
    }
    if old["hotel"]["hotel_id"] != new["hotel"]["hotel_id"]:
        out["hotel"] = {"from": old["hotel"]["name"], "to": new["hotel"]["name"],
                        "from_tier": old["hotel"]["tier"], "to_tier": new["hotel"]["tier"]}
    for k in ("outbound", "return"):
        o, n = old["transport"][k], new["transport"][k]
        if _journey(o) != _journey(n):
            out["transport"][k] = {"from": _journey(o), "to": _journey(n)}
    return out


def unchanged(d: dict) -> bool:
    return not (d["added"] or d["removed"] or d["moved"] or d["hotel"] or d["transport"] or d["delta_cost"])


def amounts(d: dict) -> set[int]:
    """Rupee figures a reply about this diff may quote."""
    return {abs(d["delta_cost"]), d["delta_cost"], d["old_total"], d["new_total"]}
