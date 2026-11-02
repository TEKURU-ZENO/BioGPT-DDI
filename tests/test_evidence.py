import json
from pathlib import Path

import httpx
import pytest

from api.ddi import evidence
from api.ddi.engine import analyze_pair
from scripts import fetch_label_evidence, import_ddinter

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DDI_DATA_DIR", str(tmp_path))
    evidence.reload()
    yield tmp_path
    evidence.reload()


def _write_ddinter(data_dir):
    import_ddinter.main([str(FIX / "ddinter_sample.csv"), "--out", str(data_dir / "external_ddi.json"),
                         "--version", "test"])
    evidence.reload()


def test_importer_keeps_resolvable_pairs_and_highest_level(data_dir):
    _write_ddinter(data_dir)
    pairs = json.loads((data_dir / "external_ddi.json").read_text())["pairs"]
    assert pairs["amoxicillin|warfarin"]["level"] == "Moderate"  # Moderate beats Minor duplicate row
    assert set(pairs["amoxicillin|warfarin"]["source_ids"]) == {"DDInter20", "DDInter1951"}
    assert "clopidogrel|pantoprazole" in pairs
    assert not any("unobtainium" in k for k in pairs)
    assert "warfarin|warfarin" not in pairs


def test_engine_without_data_is_unchanged(data_dir):
    assert analyze_pair("Amoxicillin", "Warfarin")["status"] == "no_known_interaction"


def test_external_finding_fills_gap(data_dir):
    _write_ddinter(data_dir)
    r = analyze_pair("Amoxicillin", "Warfarin")
    assert r["status"] == "interaction_found" and r["severity"] == "Moderate"
    f = r["findings"][0]
    assert f["basis"] == "external-db" and "DDInter 2.0" in f["evidence"][0]


def test_ungraded_external_record_is_minor_and_flagged(data_dir):
    _write_ddinter(data_dir)
    f = analyze_pair("Clopidogrel", "Pantoprazole")["findings"][0]
    assert f["severity"] == "Minor" and "not graded" in f["effect"]


def test_external_never_lowers_and_reports_discrepancy(data_dir):
    _write_ddinter(data_dir)
    r = analyze_pair("Sertraline", "Ibuprofen")
    assert r["severity"] == "Moderate"  # engine result kept
    assert r["severity_discrepancies"][0]["source_severity"] == "Major"


def _mock_openfda(monkeypatch):
    body = json.loads((FIX / "openfda_warfarin.json").read_text())

    def handler(request: httpx.Request):
        if "WARFARIN" in request.url.params.get("search", "").upper():
            return httpx.Response(200, json=body)
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_label_fetcher_and_excerpt(data_dir, monkeypatch):
    _mock_openfda(monkeypatch)
    fetch_label_evidence.main(["--only", "warfarin,fluconazole", "--out", str(data_dir / "label_evidence.json"),
                               "--sleep", "0"])
    labels = json.loads((data_dir / "label_evidence.json").read_text())["labels"]
    assert set(labels) == {"warfarin"}
    assert labels["warfarin"]["url"].endswith("setid=d91934a0-902e-c26c-23ca-d5accc4151b6")
    evidence.reload()

    f = analyze_pair("Warfarin", "Fluconazole")["findings"][0]
    cite = f["label_evidence"][0]
    assert cite["label_of"] == "Warfarin"
    assert cite["matched_term"] == "fluconazole" and "fluconazole" in cite["excerpt"]
    assert cite["url"].startswith("https://dailymed.nlm.nih.gov/")


def test_brand_name_matched_in_label_text(data_dir):
    (data_dir / "label_evidence.json").write_text(json.dumps({"labels": {"warfarin": {
        "set_id": "x", "title": "t", "url": "u",
        "drug_interactions": "Concomitant use with Diflucan increases INR."}}}))
    evidence.reload()
    cite = analyze_pair("Warfarin", "Fluconazole")["findings"][0]["label_evidence"][0]
    assert cite["matched_term"] == "diflucan"
