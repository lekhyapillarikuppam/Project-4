"""API-AT-03 (input violations), API-AT-04 (feasible and infeasible trips), API-AT-08 (concurrency)."""

import threading
import time
from datetime import timedelta

import pytest

from api import solver
from api.validation import today
from tripwise import variants
from tests.api.conftest import new_user

INTERESTS = {"nature": 1, "adventure": 0, "food": 4, "history": 5, "culture": 3, "spiritual": 0, "shopping": 2,
             "relaxation": 1, "nightlife": 0}


def trip(**over):
    start = today() + timedelta(days=40)
    body = {"origin": "DEL", "destination": "AGR", "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=2)).isoformat(), "people": 2, "budget_total": 30000,
            "prefs": {"daily_hours_out": 9, "interests": INTERESTS, "pace": "balanced", "comfort": "mid",
                      "modes": {"train": "neutral", "bus": "neutral", "flight": "neutral"}, "avoid_crowds": False}}
    prefs = over.pop("prefs", {})
    body.update(over)
    body["prefs"] = body["prefs"] | prefs
    return body


VIOLATIONS = [
    ("same city", trip(destination="DEL"), "destination"),
    ("unknown city", trip(origin="XYZ"), "origin"),
    ("start today", trip(start_date=today().isoformat(), end_date=(today() + timedelta(days=2)).isoformat()), "start_date"),
    ("start beyond 365", trip(start_date=(today() + timedelta(days=400)).isoformat(),
                              end_date=(today() + timedelta(days=402)).isoformat()), "start_date"),
    ("one day", trip(end_date=(today() + timedelta(days=40)).isoformat()), "end_date"),
    ("eight days", trip(end_date=(today() + timedelta(days=47)).isoformat()), "end_date"),
    ("seven people", trip(people=7), "people"),
    ("zero people", trip(people=0), "people"),
    ("budget below 2000 pp", trip(budget_total=3000), "budget_total"),
    ("budget over 10 lakh", trip(budget_total=1_000_001), "budget_total"),
    ("hours 3", trip(prefs={"daily_hours_out": 3}), "prefs.daily_hours_out"),
    ("weight 6", trip(prefs={"interests": INTERESTS | {"food": 6}}), "prefs.interests.food"),
    ("all weights 0", trip(prefs={"interests": {k: 0 for k in INTERESTS}}), "prefs.interests"),
    ("every mode avoided", trip(prefs={"modes": {"train": "avoid", "bus": "avoid", "flight": "avoid"}}), "prefs.modes"),
]


@pytest.mark.parametrize("body, field", [v[1:] for v in VIOLATIONS], ids=[v[0] for v in VIOLATIONS])
def test_api_at_03_violations(client, user, body, field):
    r = client.post("/trips", headers=user["h"], json=body)
    assert r.status_code == 422, r.text
    assert field in r.json()["fields"], r.json()


def test_per_person_budget_converted(client, user):
    body = trip()
    body.pop("budget_total")
    body["budget_per_person"] = 15000
    r = client.post("/trips", headers=user["h"], json=body)
    assert r.status_code == 201 and r.json()["request"]["budget_total"] == 30000


def test_api_at_04_feasible_and_infeasible(client, user):
    r = client.post("/trips", headers=user["h"], json=trip())
    assert r.status_code == 201, r.text
    res = r.json()["result"]
    assert res["status"] == "ok" and 1 <= len(res["variants"]) <= 3
    r = client.post("/trips", headers=user["h"], json=trip(budget_total=4000))
    assert r.status_code == 201
    res = r.json()["result"]
    assert res["status"] == "infeasible" and res["reason"] == "budget" and res["min_budget_total"] > 4000


def test_api_at_08_concurrent_creates(client, monkeypatch):
    u = new_user(client)
    live, peak, lock = [0], [0], threading.Lock()
    real = variants.plan_variants

    def counted(req, *a, **k):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        try:
            time.sleep(0.5)          # hold the slot so the three requests overlap
            return real(req, *a, **k)
        finally:
            with lock:
                live[0] -= 1

    monkeypatch.setattr("api.routers.trips.plan_variants", counted)
    codes = []

    def go():
        codes.append(client.post("/trips", headers=u["h"], json=trip()).status_code)

    threads = [threading.Thread(target=go) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(c in (201, 429) for c in codes) and 500 not in codes, codes
    assert peak[0] == 2, peak          # the requests overlapped, and no more than two solved at once
