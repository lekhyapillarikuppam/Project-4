"""007 engine extensions through the API: replan with pins, day_hours and forced transport (AI-AT-06 via 004)."""

from tests.api.test_api_trips_create import trip
from tests.api.test_api_versions import check


def test_replan_with_extensions(client, user):
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    tid = t["id"]
    v1 = client.post(f"/trips/{tid}/select", headers=user["h"], json={"variant": t["result"]["variants"][0]["variant"]}).json()
    aid = v1["plan"]["days"][0]["stops"][0]["attraction_id"]
    r = client.post(f"/trips/{tid}/replan", headers=user["h"],
                    json={"changes": {"pins": {aid: 2}, "day_hours": {"3": 5}}, "source": "chat"})
    assert r.status_code == 201, r.text
    p = check(r.json())
    assert any(s.attraction_id == aid for s in p.days[1].stops)
    assert p.days[2].window[1] == "14:00"
    r = client.post(f"/trips/{tid}/replan", headers=user["h"],
                    json={"changes": {"transport": {"out": {"mode": "bus", "class": "ACS"}}}})
    assert r.status_code == 201, r.text
    p = check(r.json())
    assert p.transport.outbound.mode == "bus"
    assert r.json()["request"]["pins"] == {aid: 2}           # earlier changes carry over
    r = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"pins": {aid: None}}})
    assert r.status_code == 201 and r.json()["request"]["pins"] == {}
    bad = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"pins": {aid: 9}}})
    assert bad.status_code == 422 and "pins" in bad.json()["fields"]
    bad = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"transport": {"out": {"mode": "boat", "class": "X"}}}})
    assert bad.status_code == 422 and "transport.out" in bad.json()["fields"]
    bad = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"day_hours": {"2": 20}}})
    assert bad.status_code == 422 and "day_hours" in bad.json()["fields"]
