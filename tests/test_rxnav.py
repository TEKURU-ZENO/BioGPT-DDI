"""RxNav fallback, exercised with a mocked transport (no network in CI)."""

import httpx
import pytest

from api.ddi import normalize

RESPONSES = {
    ("rxcui.json", "zetia"): {"idGroup": {"name": "zetia", "rxnormId": ["349556"]}},
    ("rxcui.json", "keflex"): {"idGroup": {"name": "keflex", "rxnormId": ["203172"]}},
    ("related", "349556"): {"relatedGroup": {"conceptGroup": [
        {"tty": "IN", "conceptProperties": [{"rxcui": "341248", "name": "ezetimibe", "tty": "IN"}]}]}},
    ("related", "203172"): {"relatedGroup": {"conceptGroup": [
        {"tty": "IN", "conceptProperties": [{"rxcui": "2231", "name": "cephalexin", "tty": "IN"}]}]}},
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/rxcui.json"):
        body = RESPONSES.get(("rxcui.json", request.url.params["name"]), {"idGroup": {}})
    else:
        body = RESPONSES.get(("related", path.split("/")[-2]), {"relatedGroup": {}})
    return httpx.Response(200, json=body)


@pytest.fixture
def mocked_rxnav(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(_handler), **kw))
    monkeypatch.setenv("DDI_ENABLE_RXNAV", "true")
    normalize._rxnav_ingredients.cache_clear()
    yield
    normalize._rxnav_ingredients.cache_clear()


def test_brand_resolved_via_rxnorm_to_profiled_ingredient(mocked_rxnav):
    r = normalize.resolve("Zetia")
    assert r.recognized and r.matched_via == "rxnorm" and r.ingredients == ["ezetimibe"]
    assert r.in_knowledge_base


def test_rxnorm_only_drug_reports_insufficient_data(mocked_rxnav):
    from api.ddi.engine import analyze_pair

    r = analyze_pair("Keflex", "Warfarin")
    assert r["status"] == "insufficient_data"
    assert r["severity"] == "Unknown"
    assert r["drug1"]["unknown_ingredients"] == ["cephalexin"]


def test_rxnav_failure_degrades_to_unrecognized(monkeypatch):
    def boom(**kw):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "Client", boom)
    monkeypatch.setenv("DDI_ENABLE_RXNAV", "true")
    normalize._rxnav_ingredients.cache_clear()
    assert not normalize.resolve("Zetia").recognized
    normalize._rxnav_ingredients.cache_clear()
