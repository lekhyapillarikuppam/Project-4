"""API-AT-02: user B cannot see or change user A's trip, versions, chat or replans (404, never 403)."""

from api.routers.chat import add_message
from tests.api.conftest import new_user
from tests.api.test_api_trips_create import trip


def test_api_at_02_isolation(client):
    a, b = new_user(client), new_user(client)
    t = client.post("/trips", headers=a["h"], json=trip()).json()
    tid = t["id"]
    client.post(f"/trips/{tid}/select", headers=a["h"], json={"variant": t["result"]["variants"][0]["variant"]})
    add_message(tid, "user", "hello")
    assert len(client.get(f"/trips/{tid}/chat", headers=a["h"]).json()) == 1
    calls = [("get", f"/trips/{tid}", None), ("patch", f"/trips/{tid}", {"name": "mine"}),
             ("delete", f"/trips/{tid}", None), ("post", f"/trips/{tid}/duplicate", None),
             ("post", f"/trips/{tid}/select", {"variant": "experience"}),
             ("post", f"/trips/{tid}/replan", {"changes": {"budget_total": 50000}}),
             ("get", f"/trips/{tid}/versions", None), ("get", f"/trips/{tid}/versions/1", None),
             ("post", f"/trips/{tid}/versions/1/restore", None), ("get", f"/trips/{tid}/tradeoffs", None),
             ("get", f"/trips/{tid}/chat", None)]
    for method, url, body in calls:
        r = getattr(client, method)(url, headers=b["h"], **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, url, r.status_code)
    assert client.get("/trips", headers=b["h"]).json() == []
    # A's data is untouched
    assert client.get(f"/trips/{tid}", headers=a["h"]).status_code == 200
    assert len(client.get(f"/trips/{tid}/versions", headers=a["h"]).json()) == 1
    assert client.get("/trips/not-a-uuid", headers=a["h"]).status_code == 404
