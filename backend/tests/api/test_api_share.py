"""API-AT-09: read-only share links (API-FR-14) and live-price patterns in /meta (API-FR-15)."""

from api.routers import share as share_router
from tests.api.conftest import new_user
from tests.api.test_api_trips_create import trip
from tripwise import config

PUBLIC_KEYS = {"name", "origin", "destination", "start_date", "end_date", "people", "budget_total", "version_created_at", "plan"}


def chosen_trip(client, user):
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    client.post(f"/trips/{t['id']}/select", headers=user["h"], json={"variant": t["result"]["variants"][0]["variant"]})
    return t


def test_share_create_read_revoke(client, user):
    t = chosen_trip(client, user)
    a = client.post(f"/trips/{t['id']}/share", headers=user["h"])
    b = client.post(f"/trips/{t['id']}/share", headers=user["h"])
    assert a.status_code == 200 and a.json() == b.json()                      # the same link back
    token = a.json()["token"]
    assert len(token) >= 43 and a.json()["url_path"] == f"/s/{token}"

    r = client.get(f"/shared/{token}")                                          # no Authorization header
    assert r.status_code == 200
    body = r.json()
    assert set(body) == PUBLIC_KEYS
    assert body["name"] == t["name"] and body["people"] == t["request"]["people"]
    assert "request_hash" not in body["plan"] and body["plan"]["status"] == "ok"
    text = r.text
    for private in (user["email"].lower(), user["id"], t["id"], "prefs", "locks", "excludes", "interests", "chat"):
        assert private not in text.lower(), private

    assert client.delete(f"/trips/{t['id']}/share", headers=user["h"]).status_code == 204
    assert client.get(f"/shared/{token}").status_code == 404
    new = client.post(f"/trips/{t['id']}/share", headers=user["h"]).json()["token"]
    assert new != token and client.get(f"/shared/{token}").status_code == 404   # an old link stays dead


def test_share_is_owner_only(client, user):
    t = chosen_trip(client, user)
    other = new_user(client)
    assert client.post(f"/trips/{t['id']}/share", headers=other["h"]).status_code == 404
    assert client.delete(f"/trips/{t['id']}/share", headers=other["h"]).status_code == 404
    assert client.post(f"/trips/{t['id']}/share").status_code == 401
    assert client.get("/shared/not-a-real-token").status_code == 404
    unchosen = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    assert client.post(f"/trips/{unchosen['id']}/share", headers=user["h"]).status_code == 409


def test_shared_rate_limit(client, user):
    share_router._seen.clear()
    limit = config.default().share["rate_per_minute"]
    for _ in range(limit):
        assert client.get("/shared/nope").status_code == 404
    r = client.get("/shared/nope")
    assert r.status_code == 429 and r.json()["error"] == "rate_limited"
    share_router._seen.clear()                                                  # the minute has passed
    assert client.get("/shared/nope").status_code == 404


def test_meta_has_live_price_patterns(client):
    lp = client.get("/meta").json()["live_prices"]
    assert set(lp) == {"flight", "train", "bus", "hotel"}
    assert all(v["url"].startswith("https://") and v["site"] for v in lp.values())
    assert "{checkin}" in lp["hotel"]["url"] and "{adults}" in lp["hotel"]["url"]
