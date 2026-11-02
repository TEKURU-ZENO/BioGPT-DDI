from datetime import date

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)
RX = "http://www.nlm.nih.gov/research/umls/rxnorm"


def mr(display, id_):
    return {"resourceType": "MedicationRequest", "id": id_, "status": "draft",
            "medicationCodeableConcept": {"coding": [{"system": RX, "code": "0", "display": display}]}}


def bundle(*resources):
    return {"resourceType": "Bundle", "entry": [{"resource": r} for r in resources]}


def call(drafts, active=None, patient=None, egfr=None, service="biogpt-ddi"):
    prefetch = {}
    if active is not None:
        prefetch["medications"] = bundle(*active)
    if patient:
        prefetch["patient"] = patient
    if egfr is not None:
        prefetch["egfr"] = bundle({"resourceType": "Observation", "code": {"coding": [
            {"system": "http://loinc.org", "code": "62238-1"}]}, "valueQuantity": {"value": egfr}})
    body = {"hookInstance": "x", "hook": "order-sign",
            "context": {"userId": "Practitioner/1", "patientId": "1", "draftOrders": bundle(*drafts)},
            "prefetch": prefetch}
    return client.post(f"/api/cds-services/{service}", json=body)


def test_discovery():
    services = client.get("/api/cds-services").json()["services"]
    assert {s["hook"] for s in services} == {"order-sign", "order-select"}
    assert all("medications" in s["prefetch"] for s in services)


def test_draft_vs_active_produces_critical_card():
    r = call([mr("fluconazole 150 MG Oral Tablet", "d1")], active=[mr("warfarin sodium 5 MG Oral Tablet [Coumadin]", "a1")])
    cards = r.json()["cards"]
    assert r.status_code == 200
    assert cards[0]["indicator"] == "critical"
    assert "Fluconazole" in cards[0]["summary"] or "fluconazole" in cards[0]["summary"]
    assert len(cards[0]["summary"]) <= 140
    assert cards[0]["source"]["label"].startswith("BioGPT-DDI")


def test_no_interaction_no_cards():
    cards = call([mr("amoxicillin 500 MG Oral Capsule", "d1")], active=[mr("ibuprofen 200 MG Oral Tablet", "a1")]).json()["cards"]
    assert cards == []


def test_renal_and_age_cards_from_prefetch():
    old = {"resourceType": "Patient", "birthDate": f"{date.today().year - 80}-01-01"}
    cards = call([mr("metformin 500 MG Oral Tablet", "d1"), mr("zolpidem 5 MG Oral Tablet", "d2")], active=[],
                 patient=old, egfr=25).json()["cards"]
    summaries = " ".join(c["summary"] for c in cards)
    assert "Metformin: renal dose check" in summaries
    assert "Zolpidem: potentially inappropriate" in summaries


def test_missing_prefetch_compares_drafts_and_says_so():
    cards = call([mr("simvastatin 40 MG Oral Tablet", "d1"), mr("clarithromycin 500 MG Oral Tablet", "d2")]).json()["cards"]
    assert cards[0]["indicator"] == "critical"
    assert any("Active medications were not provided" in c["summary"] for c in cards)


def test_unrecognised_draft_reported():
    cards = call([mr("unobtainium 5 MG Oral Tablet", "d1")], active=[]).json()["cards"]
    assert any("Not checked" in c["summary"] for c in cards)


def test_unknown_service_404():
    assert call([mr("warfarin", "d")], service="nope").status_code == 404
