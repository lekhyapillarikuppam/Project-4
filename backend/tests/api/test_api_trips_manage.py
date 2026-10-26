"""API-AT-06: rename, duplicate, delete (with versions and chat), list upcoming / past."""

from datetime import timedelta

from api import db
from api.validation import today
from tests.api.test_api_trips_create import trip


def test_api_at_06_manage(client, user):
    created = client.post("/trips", headers=user["h"], json=trip(name="Agra weekend")).json()
    tid = created["id"]
    assert created["name"] == "Agra weekend"
    r = client.patch(f"/trips/{tid}", headers=user["h"], json={"name": "Taj trip"})
    assert r.status_code == 200 and r.json()["name"] == "Taj trip"
    assert client.patch(f"/trips/{tid}", headers=user["h"], json={"name": "  "}).status_code == 422

    dup = client.post(f"/trips/{tid}/duplicate", headers=user["h"]).json()["request"]
    assert dup["origin"] == "DEL" and dup["destination"] == "AGR" and dup["budget_total"] == 30000
    assert len(client.get("/trips", headers=user["h"]).json()) == 1          # duplicate created nothing

    # a past trip (the API cannot create one, so insert it directly)
    past_start = today() - timedelta(days=30)
    req = dict(created["request"]) | {"start_date": past_start.isoformat(),
                                      "end_date": (past_start + timedelta(days=2)).isoformat()}
    past = db.one("INSERT INTO {s}.trips (user_id, name, request, result, start_date) VALUES (%s, %s, %s, %s, %s) "
                  "RETURNING id", user["id"], "Old trip", db.jsonb(req), db.jsonb(created["result"]), past_start)
    up = client.get("/trips?when=upcoming", headers=user["h"]).json()
    pa = client.get("/trips?when=past", headers=user["h"]).json()
    assert [t["id"] for t in up] == [tid] and [t["id"] for t in pa] == [str(past["id"])]
    assert up[0]["created_at"] == created["created_at"]                    # list items carry created_at (API-FR-06)
    assert client.get("/trips?when=later", headers=user["h"]).status_code == 422

    # newest first in each tab, and trips with no plan are left out but still open by id (API-FR-06, F10)
    newer = client.post("/trips", headers=user["h"], json=trip(name="Second trip")).json()
    infeasible = client.post("/trips", headers=user["h"], json=trip(name="Too cheap", budget_total=4000)).json()
    assert infeasible["result"]["status"] == "infeasible"
    up = client.get("/trips?when=upcoming", headers=user["h"]).json()
    assert [t["id"] for t in up] == [newer["id"], tid]
    assert all(t["status"] == "ok" for t in client.get("/trips", headers=user["h"]).json())
    assert infeasible["id"] not in [t["id"] for t in client.get("/trips", headers=user["h"]).json()]
    assert client.get(f"/trips/{infeasible['id']}", headers=user["h"]).status_code == 200
    older_past = db.one("INSERT INTO {s}.trips (user_id, name, request, result, start_date, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, now() - interval '1 day') RETURNING id",
                        user["id"], "Older past trip", db.jsonb(req), db.jsonb(created["result"]), past_start)
    pa = client.get("/trips?when=past", headers=user["h"]).json()
    assert [t["id"] for t in pa] == [str(past["id"]), str(older_past["id"])]
    for extra in (newer["id"], infeasible["id"], str(older_past["id"])):
        client.delete(f"/trips/{extra}", headers=user["h"])

    # versions and chat rows go with the trip
    plan = created["result"]["variants"][0]
    db.run("INSERT INTO {s}.plan_versions (trip_id, version, plan, request, source) VALUES (%s, 1, %s, %s, 'select')",
           tid, db.jsonb(plan), db.jsonb(created["request"]))
    db.run("INSERT INTO {s}.chat_messages (trip_id, role, text) VALUES (%s, 'user', 'hello')", tid)
    assert client.delete(f"/trips/{tid}", headers=user["h"]).status_code == 204
    assert client.get(f"/trips/{tid}", headers=user["h"]).status_code == 404
    assert db.one("SELECT count(*) AS n FROM {s}.plan_versions WHERE trip_id = %s", tid)["n"] == 0
    assert db.one("SELECT count(*) AS n FROM {s}.chat_messages WHERE trip_id = %s", tid)["n"] == 0
    assert client.delete(f"/trips/{tid}", headers=user["h"]).status_code == 404
