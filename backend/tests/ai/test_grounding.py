"""Grounding check and explanation fallback (AI-FR-02), with Groq replaced by a stub (no network)."""

import json

import pytest

from api.ai import explain, groq_client, grounding
from tests.helpers import request as req
from tripwise.models import dump
from tripwise.variants import plan_variants


@pytest.fixture(scope="module")
def plans():
    res = dump(plan_variants(req(destination="JAI", budget_total=60000)))
    assert res["status"] == "ok"
    return res["variants"]


def test_names_and_amounts(plans):
    p = plans[0]
    stop = p["days"][0]["stops"][0]["name"]
    total = p["budget"]["total"]
    assert grounding.check_plan_text(f"You visit {stop} for ₹{total:,} in all.", p, "JAI") == []
    others = grounding.city_names("JAI") - grounding.plan_names(p)
    other = sorted(others)[0]
    bad = grounding.check_plan_text(f"You visit {other} and pay Rs. {total + 7}.", p, "JAI")
    assert any(other in b for b in bad) and any("amount" in b for b in bad)
    assert grounding.amounts_in("₹1.5 lakh, Rs 20k and INR 3,400") == [150000, 20000, 3400]


def test_longest_name_wins():
    assert grounding.names_in("the Qutb Minar Complex at dusk", {"Qutb Minar", "Qutb Minar Complex"}) == {"Qutb Minar Complex"}


def test_template_is_grounded(plans):
    for p in plans:
        assert grounding.check_plan_text(explain.template(p), p, "JAI") == []


def stub(monkeypatch, replies):
    calls = []

    def chat(messages, **kw):
        calls.append(messages)
        r = replies[len(calls) - 1]
        if isinstance(r, Exception):
            raise r
        return {"content": json.dumps(r)}
    monkeypatch.setattr(groq_client, "chat", chat)
    return calls


def test_retry_then_template(monkeypatch, plans):
    request = req(destination="JAI", budget_total=60000).model_dump(mode="json", by_alias=True)
    good = {p["variant"]: f"A good fit at ₹{p['budget']['total']:,}." for p in plans}
    bad = {v: "Includes a free helicopter ride for ₹1." for v in good}
    names = list(good)
    # first call: one variant bad; second call: still bad -> template for that one only
    calls = stub(monkeypatch, [good | {names[0]: bad[names[0]]}, {names[0]: bad[names[0]]}])
    out = explain.explain(request, plans)
    assert len(calls) == 2 and out["calls"] == 2
    assert out["source"][names[0]] == "template" and all(out["source"][v] == "llm" for v in names[1:])
    for p in plans:
        assert grounding.check_plan_text(out["texts"][p["variant"]], p, "JAI") == []
    # first call good -> one call only
    calls = stub(monkeypatch, [good])
    assert explain.explain(request, plans)["calls"] == 1 and len(calls) == 1
    # first call fails -> Unavailable for the caller
    stub(monkeypatch, [groq_client.Unavailable("x")])
    with pytest.raises(groq_client.Unavailable):
        explain.explain(request, plans)
