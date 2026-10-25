"""AI-AT-05: with no Groq key, planning works, parse is 503, explanations are omitted with a notice and chat says
it is unavailable without changing anything (AI-FR-06). Also the per-user chat rate limit (AI-FR-07)."""

from api.routers import chat as chat_router
from tests.api.test_api_trips_create import trip
from tripwise import config


def test_ai_at_05_no_key(client, user, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")          # load_dotenv does not override a set variable
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000))
    assert t.status_code == 201 and t.json()["result"]["status"] == "ok"           # planning never needs Groq
    tid = t.json()["id"]
    r = client.post("/ai/parse-prefs", headers=user["h"], json={"text": "Two of us, beaches and food"})
    assert r.status_code == 503 and "sliders" in r.json()["message"]
    r = client.get(f"/trips/{tid}/explanations", headers=user["h"]).json()
    assert r["status"] == "unavailable" and r["notice"]
    assert "explanations" not in client.get(f"/trips/{tid}", headers=user["h"]).json()["result"]   # not cached
    v = t.json()["result"]["variants"][0]["variant"]
    assert client.post(f"/trips/{tid}/select", headers=user["h"], json={"variant": v}).status_code == 201
    r = client.post(f"/trips/{tid}/chat", headers=user["h"], json={"message": "only 5 hours on day 2"})
    assert r.status_code == 201
    out = r.json()
    assert out["version"] is None and "unavailable" in out["assistant"]["text"]
    assert len(client.get(f"/trips/{tid}/versions", headers=user["h"]).json()) == 1
    r = client.post(f"/trips/{tid}/replan", headers=user["h"], json={"changes": {"day_hours": {"2": 5}}})
    assert r.status_code == 201                                                      # the form path still works


def test_chat_rate_limit(client, user, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    client.post(f"/trips/{t['id']}/select", headers=user["h"], json={"variant": t["result"]["variants"][0]["variant"]})
    limit = config.default().chat["rate_per_hour"]
    for _ in range(limit):
        assert client.post(f"/trips/{t['id']}/chat", headers=user["h"], json={"message": "hi"}).status_code == 201
    r = client.post(f"/trips/{t['id']}/chat", headers=user["h"], json={"message": "hi"})
    assert r.status_code == 429 and r.json()["error"] == "rate_limited"
    chat_router._sent[user["id"]].clear()                                           # the window has passed
    assert client.post(f"/trips/{t['id']}/chat", headers=user["h"], json={"message": "hi"}).status_code == 201
