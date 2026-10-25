"""API-AT-05: select → replan with an exclude → restore v1; plus budget/prefs replans and trade-offs cache."""

from tripwise import data
from tripwise.models import Plan, TripRequest
from validator.validate import validate
from tripwise import config
from tests.api.test_api_trips_create import trip


def check(v):
    p = Plan.model_validate(v["plan"])
    req = TripRequest.model_validate(v["request"])
    assert validate(p, req, data.default(), config.default().as_dict()) == [], v["version"]
    return p


def test_api_at_05_select_replan_restore(client, user):
    t = client.post("/trips", headers=user["h"], json=trip()).json()
    tid = t["id"]
    variant = t["result"]["variants"][0]["variant"]
    assert client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"budget_total": 40000}}).status_code == 409
    v1 = client.post(f"/trips/{tid}/select", headers=user["h"], json={"variant": variant})
    assert v1.status_code == 201 and v1.json()["version"] == 1
    p1 = check(v1.json())
    gone = p1.activity_ids()[0]
    v2 = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"excludes": [gone]}, "note": "no thanks"})
    assert v2.status_code == 201, v2.text
    assert v2.json()["version"] == 2 and v2.json()["changes"] == {"excludes": [gone]}
    p2 = check(v2.json())
    assert gone not in p2.activity_ids()
    v3 = client.post(f"/trips/{tid}/versions/1/restore", headers=user["h"])
    assert v3.status_code == 201 and v3.json()["version"] == 3 and v3.json()["source"] == "restore"
    assert v3.json()["plan"] == v1.json()["plan"]
    check(v3.json())
    lst = client.get(f"/trips/{tid}/versions", headers=user["h"]).json()
    assert [v["version"] for v in lst] == [1, 2, 3] and [v["source"] for v in lst] == ["select", "replan", "restore"]
    assert client.get(f"/trips/{tid}/versions/2", headers=user["h"]).json()["plan"] == v2.json()["plan"]
    assert client.get(f"/trips/{tid}/versions/9", headers=user["h"]).status_code == 404


def test_replan_budget_prefs_and_errors(client, user):
    t = client.post("/trips", headers=user["h"], json=trip()).json()
    tid = t["id"]
    client.post(f"/trips/{tid}/select", headers=user["h"], json={"variant": t["result"]["variants"][0]["variant"]})
    r = client.post(f"/trips/{tid}/replan", headers=user["h"],
                    json={"changes": {"prefs": {"pace": "relaxed", "interests": {"food": 0}}}, "source": "chat"})
    assert r.status_code == 201 and r.json()["request"]["prefs"]["pace"] == "relaxed"
    assert r.json()["request"]["prefs"]["interests"]["food"] == 0 and r.json()["request"]["prefs"]["interests"]["history"] == 5
    check(r.json())
    r = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"budget_total": 4000}})
    assert r.status_code == 409 and r.json()["error"] == "infeasible" and r.json()["result"]["min_budget_total"] > 4000
    assert len(client.get(f"/trips/{tid}/versions", headers=user["h"]).json()) == 2     # nothing stored
    r = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"weather": "sunny"}})
    assert r.status_code == 422
    r = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"prefs": {"daily_hours_out": 30}}})
    assert r.status_code == 422 and "prefs.daily_hours_out" in r.json()["fields"]


def test_tradeoffs_cached(client, user):
    t = client.post("/trips", headers=user["h"], json=trip()).json()
    tid = t["id"]
    first = client.get(f"/trips/{tid}/tradeoffs?variant=balanced", headers=user["h"])
    assert first.status_code == 200 and first.json()["cached"] is False and len(first.json()["rows"]) == 4
    second = client.get(f"/trips/{tid}/tradeoffs?variant=balanced", headers=user["h"]).json()
    assert second["cached"] is True and second["rows"] == first.json()["rows"]
    assert client.get(f"/trips/{tid}/tradeoffs?variant=cheap", headers=user["h"]).status_code == 422
