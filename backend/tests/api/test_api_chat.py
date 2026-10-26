"""POST /trips/{id}/chat with Groq replaced by a stub (AI-FR-03–AI-FR-06): tool → change set → engine version,
diff, grounded reply or template, clarifying replies, unsupported, why, and Groq unavailable."""

import json

import pytest

from api.ai import chat, diff as diffs, groq_client
from tests.api.test_api_trips_create import trip
from tests.api.test_api_versions import check
from tripwise import config, data


def tool(fn, **args):
    return {"tool_calls": [{"id": "c1", "type": "function", "function": {"name": fn, "arguments": json.dumps(args)}}]}


class Stub:
    """Groq stand-in: a call with tools returns the next queued message; a reply call returns `reply`."""

    def __init__(self, monkeypatch, reply="Done."):
        self.queue, self.reply, self.calls, self.kw = [], reply, 0, []
        monkeypatch.setattr(groq_client, "chat", self)

    def __call__(self, messages, **kw):
        self.calls += 1
        self.kw.append(kw)
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
    assert s.calls <= 2 * len(cases)                                # at most 2 Groq calls per message


def first_stop(client, user, tid):
    return client.get(f"/trips/{tid}/versions/1", headers=user["h"]).json()["plan"]["days"][0]["stops"][0]["name"]


def test_ungrounded_reply_uses_template(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch, reply="Added a sunset camel safari for ₹999999.")
    s.queue.append(tool("exclude_activity", names=[first_stop(client, user, chosen)]))   # a change that alters the plan
    a = say(client, user, chosen, "drop the first stop")["assistant"]
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


def stops(plan):
    return [s["attraction_id"] for d in plan["days"] for s in d["stops"]]


def of_kind(kind):
    return [a for a in data.default().by_city["JAI"] if a.kind == kind]


def test_limit_kind_max_0_keeps_every_one_out(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    s.queue.append(tool("limit_kind", limits=[{"kind": "temple", "max": 0}]))
    out = say(client, user, chosen, "no temples please")
    v = out["version"]
    check(v)
    temples = {a.attraction_id for a in of_kind("temple")}
    assert temples and temples <= set(v["request"]["excludes"])          # in the plan or not, all kept out
    assert not temples & set(stops(v["plan"]))


def test_limit_kind_max_1_keeps_the_best_in_the_plan(client, user, chosen, monkeypatch):
    from tripwise import value
    from tripwise.models import Prefs
    s = Stub(monkeypatch)
    plan = client.get(f"/trips/{chosen}/versions/1", headers=user["h"]).json()
    in_plan = stops(plan["plan"])
    kind = next(k for k in sorted({a.kind for a in data.default().by_city["JAI"]})
                if sum(a.attraction_id in in_plan for a in of_kind(k)) >= 2)       # a kind with 2+ places in the plan
    places = [a for a in of_kind(kind) if a.attraction_id in in_plan]
    prefs = Prefs.model_validate(plan["request"]["prefs"])
    best = max(places, key=lambda a: value.activity(a, prefs, config.default())).attraction_id
    s.queue.append(tool("limit_kind", limits=[{"kind": kind, "max": 1}]))
    v = say(client, user, chosen, f"only one {kind}")["version"]
    check(v)
    assert best not in v["request"]["excludes"]
    every = {a.attraction_id for a in of_kind(kind)}
    assert every - {best} <= set(v["request"]["excludes"])
    assert [i for i in stops(v["plan"]) if i in every] in ([best], [])


@pytest.mark.parametrize("kind", ["spaceport", "beach"])            # unknown anywhere; no beach in Jaipur
def test_limit_kind_not_in_city_changes_nothing(client, user, chosen, monkeypatch, kind):
    s = Stub(monkeypatch)
    s.queue.append(tool("limit_kind", limits=[{"kind": kind, "max": 0}]))
    out = say(client, user, chosen, f"no {kind}")
    a = out["assistant"]
    assert a["actions"]["kind"] == "no_change" and out["version"] is None
    assert kind in a["text"] and "Jaipur" in a["text"] and "nothing changed" in a["text"]
    assert s.calls == 1 and len(versions(client, user, chosen)) == 1    # no replan, no call 2


def test_no_op_change_runs_no_replan(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    pace = client.get(f"/trips/{chosen}/versions/1", headers=user["h"]).json()["request"]["prefs"]["pace"]
    s.queue.append(tool("set_pace", pace=pace))
    a = say(client, user, chosen, "same pace")["assistant"]
    assert a["actions"]["kind"] == "no_change" and "Nothing changed" in a["text"] and "Done" not in a["text"]
    s.queue.append(tool("exclude_activity", names=["Hawa Mahal"]))
    say(client, user, chosen, "drop hawa mahal")
    s.queue.append(tool("exclude_activity", names=["Hawa Mahal"]))
    a = say(client, user, chosen, "drop hawa mahal again")["assistant"]
    assert a["actions"]["kind"] == "no_change"
    assert len(versions(client, user, chosen)) == 2                     # only the first exclude made a version


def test_empty_diff_never_says_done(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    s.queue.append(tool("regenerate"))
    out = say(client, user, chosen, "plan it again")
    a = out["assistant"]
    assert a["actions"]["reply"] == "no_change" and a["text"].startswith("Your plan did not change")
    assert "Done" not in a["text"] and s.calls == 1                     # call 2 skipped


def test_exclude_takes_a_list_and_names_what_it_did_not_change(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    s.queue.append(tool("exclude_activity", names=["Hawa Mahal", "Jal Mahal"]))
    v = say(client, user, chosen, "drop hawa mahal and jal mahal")["version"]
    assert {"JAI-A-01", chat.resolve("Jal Mahal", "JAI")[0]} <= set(v["request"]["excludes"])
    s.queue.append(tool("exclude_activity", names=["Amber Fort"]))
    out = say(client, user, chosen, "skip Amber Fort and Albert Hall Museum")
    a, d = out["assistant"], out["assistant"]["actions"]["diff"]
    touched = set(d["added"]) | set(d["removed"]) | {m["name"] for m in d["moved"]}
    if "Albert Hall Museum" not in touched:
        assert a["text"].endswith("I didn't change Albert Hall Museum; ask again naming it if you want.")


def test_reply_facts_hold_no_message():
    facts = chat.reply_facts(2, {"budget_total": 50000}, {"added": [], "removed": [], "moved": [], "hotel": None,
                             "transport": {}, "delta_cost": 0}, {"excludes": ["JAI-A-01"]}, {"excludes": [], "prefs": {}},
                             [{"name": "exclude_activity", "args": {"names": ["Hawa Mahal"]}}])
    assert "request" not in facts and facts["applied"] == {"removed_and_kept_out": ["Hawa Mahal"]}


def test_deadline_call1_timeout_is_unavailable(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    s.queue.append(groq_client.Unavailable("ReadTimeout"))
    a = say(client, user, chosen, "add a fort")["assistant"]
    assert a["actions"]["kind"] == "unavailable" and a["version"] is None
    assert s.calls == 1 and s.kw[0]["timeout"] == config.default().groq["timeout_tools_s"]
    assert len(versions(client, user, chosen)) == 1


def test_deadline_call2_gets_the_rest(client, user, chosen, monkeypatch):
    s = Stub(monkeypatch)
    s.queue.append(tool("exclude_activity", names=[first_stop(client, user, chosen)]))
    a = say(client, user, chosen, "drop the first stop")["assistant"]
    assert a["actions"]["reply"] == "llm" and s.calls == 2
    assert 1 <= s.kw[1]["timeout"] <= config.default().chat["deadline_s"] - 0.5


def test_deadline_skips_call2_under_1s(client, user, chosen, monkeypatch):
    import copy
    s = Stub(monkeypatch)
    raw = copy.deepcopy(config.default().as_dict())
    raw["chat"]["deadline_s"] = 1.2                                     # less than 1 s left after re-planning
    short = config.Config(raw, config.default().path)
    monkeypatch.setattr(config, "default", lambda: short)
    s.queue.append(tool("exclude_activity", names=[first_stop(client, user, chosen)]))
    out = say(client, user, chosen, "drop the first stop")
    a = out["assistant"]
    assert a["actions"]["reply"] == "template" and a["text"].startswith("Done, this is version")
    assert s.calls == 1 and out["version"]["version"] == 2               # the change itself is made


def test_client_stops_at_deadline(monkeypatch):
    import time
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(groq_client.httpx, "post", lambda *a, **k: pytest.fail("no request after the deadline"))
    with pytest.raises(groq_client.Unavailable):
        groq_client.chat([{"role": "user", "content": "hi"}], temperature=0, deadline=time.perf_counter() - 1)


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
