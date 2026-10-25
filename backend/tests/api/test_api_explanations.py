"""GET /trips/{id}/explanations (AI-FR-02, AI-FR-06) with Groq replaced by a stub."""

import json

from api.ai import groq_client
from tests.api.test_api_trips_create import trip


def test_explanations_cached_and_unavailable(client, user, monkeypatch):
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    tid = t["id"]
    monkeypatch.setattr(groq_client, "chat", lambda *a, **k: (_ for _ in ()).throw(groq_client.Unavailable("no key")))
    r = client.get(f"/trips/{tid}/explanations", headers=user["h"])
    assert r.status_code == 200 and r.json()["status"] == "unavailable" and r.json()["notice"]
    texts = {p["variant"]: f"Costs ₹{p['budget']['total']:,} in all." for p in t["result"]["variants"]}
    calls = []
    monkeypatch.setattr(groq_client, "chat", lambda *a, **k: calls.append(1) or {"content": json.dumps(texts)})
    r = client.get(f"/trips/{tid}/explanations", headers=user["h"]).json()
    assert r["status"] == "ok" and r["texts"] == texts and r["cached"] is False
    r = client.get(f"/trips/{tid}/explanations", headers=user["h"]).json()
    assert r["cached"] is True and len(calls) == 1
    assert client.get(f"/trips/{tid}", headers=user["h"]).json()["result"]["explanations"]["texts"] == texts


def test_explanations_other_user_404(client, user):
    from tests.api.conftest import new_user
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    other = new_user(client)
    assert client.get(f"/trips/{t['id']}/explanations", headers=other["h"]).status_code == 404
