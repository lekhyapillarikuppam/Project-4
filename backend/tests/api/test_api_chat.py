"""POST /trips/{id}/chat with Groq replaced by a stub (AI-FR-03–AI-FR-06): tool → change set → engine version,
diff, grounded reply or template, clarifying replies, unsupported, why, and Groq unavailable."""

import json

import pytest

from api.ai import chat, diff as diffs, groq_client
from tests.api.test_api_trips_create import trip
from tests.api.test_api_versions import check
from tripwise import data


def tool(fn, **args):
    return {"tool_calls": [{"id": "c1", "type": "function", "function": {"name": fn, "arguments": json.dumps(args)}}]}


class Stub:
    """Groq stand-in: a call with tools returns the next queued message; a reply call returns `reply`."""

    def __init__(self, monkeypatch, reply="Done."):
        self.queue, self.reply, self.calls = [], reply, 0
        monkeypatch.setattr(groq_client, "chat", self)

    def __call__(self, messages, **kw):
        self.calls += 1
        if kw.get("tools"):
            r = self.queue.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        return {"content": self.reply}


@pytest.fixture
def chosen(client, user):
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    client.post(f"/trips/{t['id']}/select", headers=user["h"], json={"variant": t["result"]["variants"][0]["variant"]})
    return t["id"]


def say(client, user, tid, text):
    r = client.post(f"/trips/{tid}/chat", headers=user["h"], json={"message": text})
    assert r.status_code == 201, r.text
    return r.json()


def versions(client, user, tid):
    return client.get(f"/trips/{tid}/versions", headers=user["h"]).json()


def test_change_tools_make_versions(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    tid = chosen
    plan1 = client.get(f"/trips/{tid}/versions/1", headers=user["h"]).json()["plan"]
    first = plan1["days"][0]["stops"][0]
    cases = [
        (tool("lock_activity", name="nahargarh fort"), lambda r: "JAI-A-06" in r["locks"]),
        (tool("exclude_activity", name=first["name"]), lambda r: first["attraction_id"] in r["excludes"]),
        (tool("set_budget", budget_total=60000), lambda r: r["budget_total"] == 60000),
        (tool("set_day_hours", day=2, hours=5), lambda r: r["day_hours"] == {"2": 5}),
        (tool("set_all_hours", hours=8), lambda r: r["prefs"]["daily_hours_out"] == 8 and r["day_hours"] == {}),
        (tool("set_hotel_tier", tier="budget"), lambda r: r["prefs"]["comfort"] == "budget"),
        (tool("set_pace", pace="relaxed"), lambda r: r["prefs"]["pace"] == "relaxed"),
        (tool("set_interest", interest="food", weight=5), lambda r: r["prefs"]["interests"]["food"] == 5),
        (tool("move_activity", name="Hawa Mahal", day=3), lambda r: r["pins"].get("JAI-A-01") == 3),
        (tool("set_transport", direction="ret", mode="train"), lambda r: r["transport"]["ret"] == {"mode": "train", "class": "3A"}),
        (tool("regenerate"), lambda r: True),
    ]
    for msg, ok in cases:
        s.queue.append(msg)
        out = say(client, user, tid, "change")
        a = out["assistant"]
        assert a["actions"]["kind"] == "change", a
        v = out["version"]
        check(v)                                                    # every chat version passes the validator
        assert ok(v["request"]), (msg, v["request"])
        prev = client.get(f"/trips/{tid}/versions/{v['version'] - 1}", headers=user["h"]).json()
        assert a["actions"]["diff"] == diffs.diff(prev["plan"], v["plan"])   # the reply's diff is the real one
        assert a["version"] == v["version"] and v["source"] == "chat"
    assert s.calls == 2 * len(cases)                                # at most 2 Groq calls per message


def test_ungrounded_reply_uses_template(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch, reply="Added a sunset camel safari for ₹999999.")
    s.queue.append(tool("set_budget", budget_total=70000))
    a = say(client, user, chosen, "more budget")["assistant"]
    assert a["actions"]["reply"] == "template" and "999999" not in a["text"] and a["text"].startswith("Done, this is version")


def test_clarify_unsupported_why(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch, reply="It nearly made it.")
    n = len(versions(client, user, chosen))
    s.queue.append(tool("lock_activity", name="temple"))
    a = say(client, user, chosen, "keep the temple")["assistant"]
    assert a["actions"]["kind"] == "clarify" and "Which one" in a["text"]
    s.queue.append(tool("exclude_activity", name="Eiffel Tower"))
    assert "couldn't find" in say(client, user, chosen, "drop eiffel")["assistant"]["text"]
    s.queue.append(tool("move_activity", name="Hawa Mahal", day=9))
    assert "days 1 to" in say(client, user, chosen, "move to day 9")["assistant"]["text"]
    s.queue.append(tool("unsupported", topic="booking", closest="set_hotel_tier"))
    a = say(client, user, chosen, "book my hotel")["assistant"]
    assert a["actions"]["kind"] == "unsupported" and "hotel level" in a["text"]
    s.queue.append(tool("explain", name="Hawa Mahal"))
    a = say(client, user, chosen, "why hawa mahal?")["assistant"]
    assert a["actions"]["kind"] == "why" and a["version"] is None
    s.queue.append(tool("explain"))
    assert say(client, user, chosen, "why this plan?")["assistant"]["actions"]["kind"] == "why"
    assert len(versions(client, user, chosen)) == n                 # none of these changed the plan


def test_why_trial_is_not_saved(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch, reply="It would fit.")
    plan = client.get(f"/trips/{chosen}/versions/1", headers=user["h"]).json()["plan"]
    seen = ({st["attraction_id"] for d in plan["days"] for st in d["stops"]}
            | {m["attraction_id"] for m in plan["near_misses"]})
    other = next(a for a in data.default().attractions.values() if a.city_id == "JAI" and a.attraction_id not in seen)
    s.queue.append(tool("explain", name=other.name))
    a = say(client, user, chosen, f"why not {other.name}?")["assistant"]
    assert a["actions"]["kind"] == "why" and "would" in a["actions"]["facts"]["status"]
    assert len(versions(client, user, chosen)) == 1


def test_unavailable_and_infeasible(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    s.queue.append(groq_client.Unavailable("timeout"))
    a = say(client, user, chosen, "add a fort")["assistant"]
    assert a["actions"]["kind"] == "unavailable" and "unavailable" in a["text"]
    s.queue.append(tool("set_transport", direction="both", mode="flight"))      # no DEL-JAI flights in the data
    a = say(client, user, chosen, "fly both ways")["assistant"]
    assert a["actions"]["kind"] == "infeasible" and "unchanged" in a["text"]
    s.queue.append(tool("set_budget", budget_total=2000))                      # under the minimum: field error
    a = say(client, user, chosen, "budget 2000")["assistant"]
    assert a["actions"]["kind"] == "clarify" and "isn't possible" in a["text"]
    assert len(versions(client, user, chosen)) == 1
    hist = client.get(f"/trips/{chosen}/chat", headers=user["h"]).json()
    assert [m["role"] for m in hist] == ["user", "assistant"] * 3


def test_chat_needs_selection_and_owner(client, user, monkeypatch):
    from tests.api.conftest import new_user
    Stub(monkeypatch)
    t = client.post("/trips", headers=user["h"], json=trip(destination="JAI", budget_total=50000)).json()
    assert client.post(f"/trips/{t['id']}/chat", headers=user["h"], json={"message": "hi"}).status_code == 409
    other = new_user(client)
    assert client.post(f"/trips/{t['id']}/chat", headers=other["h"], json={"message": "hi"}).status_code == 404
    assert client.post(f"/trips/{t['id']}/chat", headers=user["h"], json={"message": ""}).status_code == 422


def test_resolve_names():
    assert chat.resolve("hawa mahal", "JAI")[0] == "JAI-A-01"
    assert chat.resolve("Nahargarh", "JAI")[0] == "JAI-A-06"
    assert chat.resolve("amber fort palace", "JAI")[0] == "JAI-A-02"
    with pytest.raises(chat.Clarify):
        chat.resolve("temple", "JAI")
