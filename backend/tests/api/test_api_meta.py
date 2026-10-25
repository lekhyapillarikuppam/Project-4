"""Public endpoints: health, meta, cities, places."""


def test_public_endpoints(client):
    assert client.get("/health").json()["status"] == "ok"
    m = client.get("/meta").json()
    assert m["estimate_label"].startswith("Estimated prices, compiled") and len(m["interests"]) == 9
    assert len(client.get("/cities").json()) == 15
    p = client.get("/cities/JAI/places").json()
    assert p["attractions"] and p["hotels"] and {"id", "lat", "lon"} <= set(p["attractions"][0])
    assert client.get("/cities/XYZ/places").status_code == 404
