from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["knowledge_base"]["ingredients"] > 100


def test_predict_shape():
    r = client.post("/api/predict", json={"drug1": "Warfarin", "drug2": "Fluconazole"})
    assert r.status_code == 200
    body = r.json()
    for key in ("status", "severity", "prediction", "findings", "patient_report", "professional_report",
                "disclaimer", "kb_version", "drug1", "drug2"):
        assert key in body
    assert body["severity"] == "Major"
    assert "Fluconazole" in body["professional_report"]


def test_predict_unrecognized():
    body = client.post("/api/predict", json={"drug1": "Water", "drug2": "Sugar"}).json()
    assert body["status"] == "unrecognized_drug"
    assert body["severity"] == "Unknown"


def test_predict_rejects_bad_input():
    assert client.post("/api/predict", json={"drug1": "", "drug2": "x"}).status_code == 422
    assert client.post("/api/predict", json={"drug1": "a" * 101, "drug2": "x"}).status_code == 422
    assert client.post("/api/predict", json={"drug1": "<script>", "drug2": "x"}).status_code == 422


def test_regimen():
    body = client.post("/api/regimen", json={"drugs": ["Warfarin", "Fluconazole", "Ibuprofen"]}).json()
    assert body["highest_severity"] == "Major"
    assert len(body["pairs"]) == 3


def test_pdf_patient_and_professional():
    for kind in ("patient", "professional"):
        r = client.post("/api/generate-pdf", json={"drug1": "Warfarin", "drug2": "Aspirin", "report_type": kind})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"


def test_pdf_ignores_client_supplied_prediction():
    forged = {"severity": "Minor", "patient_report": "Totally safe", "findings": []}
    r = client.post("/api/generate-pdf", json={"drug1": "Warfarin", "drug2": "Aspirin", "report_type": "patient",
                                               "prediction_data": forged})
    assert r.status_code == 200  # server re-derives; forged payload is ignored


def test_pdf_filename_is_sanitised():
    r = client.post("/api/generate-pdf", json={"drug1": "Warfarin", "drug2": "Aspirin 81 mg", "report_type": "patient"})
    cd = r.headers["content-disposition"]
    assert cd == 'attachment; filename="DDI_Report_Patient_Warfarin_Aspirin_81_mg.pdf"'


def test_pdf_rejects_unknown_report_type():
    r = client.post("/api/generate-pdf", json={"drug1": "Warfarin", "drug2": "Aspirin", "report_type": "x"})
    assert r.status_code == 422


def test_pdf_for_unrecognized_drug_still_renders():
    r = client.post("/api/generate-pdf", json={"drug1": "O'Brien's tonic", "drug2": "Aspirin",
                                               "report_type": "professional"})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
