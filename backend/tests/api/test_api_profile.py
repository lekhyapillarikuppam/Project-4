"""Profile (API-FR-03): a blank profile before saving, save and reload, invalid prefs rejected."""

PREFS = {"daily_hours_out": 10, "pace": "packed", "comfort": "budget", "avoid_crowds": True,
         "modes": {"train": "preferred", "bus": "avoid", "flight": "neutral"},
         "interests": {"nature": 4, "adventure": 2, "food": 5, "history": 1, "culture": 0, "spiritual": 0,
                       "shopping": 0, "relaxation": 3, "nightlife": 1}}


def test_profile_round_trip(client, user):
    r = client.get("/profile", headers=user["h"])
    assert r.status_code == 200 and r.json()["saved"] is False
    blank = r.json()["prefs"]                                     # nothing invented for a new user
    assert blank["daily_hours_out"] is None and blank["pace"] is None and blank["comfort"] is None
    assert set(blank["interests"].values()) == {0} and len(blank["interests"]) == 9
    assert blank["modes"] == {"train": "neutral", "bus": "neutral", "flight": "neutral"} and blank["avoid_crowds"] is False
    r = client.put("/profile", headers=user["h"], json={"prefs": blank})       # a blank profile cannot be saved
    assert r.status_code == 422
    assert {"prefs.daily_hours_out", "prefs.pace", "prefs.comfort", "prefs.interests"} <= set(r.json()["fields"])
    r = client.put("/profile", headers=user["h"], json={"prefs": PREFS})
    assert r.status_code == 200 and r.json()["prefs"] == PREFS
    r = client.get("/profile", headers=user["h"])
    assert r.json()["saved"] is True and r.json()["prefs"] == PREFS


def test_profile_rejects_bad_prefs(client, user):
    bad = PREFS | {"daily_hours_out": 20, "modes": {"train": "avoid", "bus": "avoid", "flight": "avoid"}}
    r = client.put("/profile", headers=user["h"], json={"prefs": bad})
    assert r.status_code == 422
    assert {"prefs.daily_hours_out", "prefs.modes"} <= set(r.json()["fields"])
    assert client.get("/profile").status_code == 401
