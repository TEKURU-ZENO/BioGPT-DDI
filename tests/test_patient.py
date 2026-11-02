import pytest
from fastapi.testclient import TestClient

from api.ddi.engine import analyze_pair, analyze_regimen
from api.ddi.lexicon import DRUGS
from api.ddi.patient import Patient
from api.ddi.pgx import functional_phenotypes
from api.index import app


def titles(alerts):
    return [a["title"] for a in alerts]


# ------------------------------------------------------------------ renal
@pytest.mark.parametrize("egfr,level", [(25, "critical"), (40, "warning"), (60, None)])
def test_metformin_renal_thresholds(egfr, level):
    alerts = [a for a in analyze_pair("Metformin", "Atorvastatin", Patient(egfr=egfr))["patient_alerts"]
              if a["drug"] == "Metformin"]
    assert (alerts[0]["level"] if alerts else None) == level


def test_crcl_based_labels_are_flagged_as_approximate():
    a = analyze_pair("Dabigatran", "Metformin", Patient(egfr=25))["patient_alerts"]
    dabi = next(x for x in a if x["drug"] == "Dabigatran")
    assert "creatinine clearance" in dabi["message"]


def test_nsaid_ace_escalates_with_low_egfr():
    assert analyze_pair("Lisinopril", "Ibuprofen")["severity"] == "Moderate"
    r = analyze_pair("Lisinopril", "Ibuprofen", Patient(egfr=40))
    assert r["severity"] == "Major"
    assert r["findings"][0]["escalated_from"] == "Moderate"


def test_hyperkalaemia_escalates_below_45():
    assert analyze_pair("Lisinopril", "Spironolactone", Patient(egfr=35))["severity"] == "Major"
    assert analyze_pair("Lisinopril", "Spironolactone", Patient(egfr=70))["severity"] == "Moderate"


def test_colchicine_inhibitor_contraindicated_in_renal_impairment():
    assert analyze_pair("Colchicine", "Clarithromycin", Patient(egfr=50))["severity"] == "Contraindicated"


# ------------------------------------------------------------------ age (Beers)
def test_beers_alerts_only_for_65_plus():
    young = analyze_pair("Zolpidem", "Metformin", Patient(age=40))["patient_alerts"]
    old = analyze_pair("Zolpidem", "Metformin", Patient(age=70))["patient_alerts"]
    assert young == []
    assert any(a["drug"] == "Zolpidem" and a["category"] == "age" for a in old)


def test_most_specific_beers_entry_wins():
    a = [x for x in analyze_pair("Indomethacin", "Metformin", Patient(age=80))["patient_alerts"]
         if x["drug"] == "Indomethacin"]
    assert len(a) == 1 and "highest risk" in a[0]["message"]


# ------------------------------------------------------------------ PGx / phenoconversion
def test_phenoconversion_rules():
    p = [DRUGS["paroxetine"]]
    assert functional_phenotypes({"CYP2D6": "NM"}, p)["CYP2D6"].functional == "PM"     # strong inhibitor
    assert functional_phenotypes({"CYP2D6": "NM"}, [DRUGS["duloxetine"]])["CYP2D6"].functional == "IM"  # moderate
    assert functional_phenotypes({"CYP2C19": "NM"}, [DRUGS["rifampin"]])["CYP2C19"].functional == "RM"   # inducer
    assert functional_phenotypes({"CYP2D6": "NM"}, [DRUGS["rifampin"]])["CYP2D6"].functional == "NM"     # 2D6 not inducible


def test_clopidogrel_poor_metabolizer_genotype():
    a = analyze_pair("Clopidogrel", "Aspirin", Patient(pgx={"CYP2C19": "PM"}))["patient_alerts"]
    assert a[0]["level"] == "critical" and a[0]["category"] == "drug-gene"
    assert "prasugrel or ticagrelor" in a[0]["message"]


def test_codeine_phenoconverted_by_paroxetine():
    r = analyze_regimen(["Codeine", "Paroxetine"], Patient(pgx={"CYP2D6": "NM"}))
    codeine = next(a for a in r["patient_alerts"] if a["drug"] == "Codeine")
    assert codeine["category"] == "drug-drug-gene" and "Paroxetine" in codeine["message"]
    assert r["phenotypes"]["CYP2D6"]["phenoconverted"] is True


def test_drug_does_not_phenoconvert_itself():
    a = analyze_regimen(["Paroxetine", "Metformin"], Patient(pgx={"CYP2D6": "NM"}))["patient_alerts"]
    assert not any(x["drug"] == "Paroxetine" for x in a)


def test_genotype_changes_ddi_interpretation():
    f = analyze_pair("Metoprolol", "Paroxetine", Patient(pgx={"CYP2D6": "PM"}))["findings"][0]
    assert any("poor metabolizer" in n for n in f["patient_notes"])


def test_no_patient_means_no_patient_fields():
    r = analyze_pair("Warfarin", "Fluconazole")
    assert "patient_alerts" not in r


# ------------------------------------------------------------------ API
client = TestClient(app)


def test_api_patient_validation():
    ok = client.post("/api/predict", json={"drug1": "Codeine", "drug2": "Paroxetine",
                                           "patient": {"age": 70, "egfr": 50, "pgx": {"cyp2d6": "um"}}})
    assert ok.status_code == 200 and ok.json()["phenotypes"]["CYP2D6"]["genetic"] == "UM"
    bad_gene = client.post("/api/predict", json={"drug1": "a", "drug2": "b", "patient": {"pgx": {"CYP3A5": "PM"}}})
    bad_pheno = client.post("/api/predict", json={"drug1": "a", "drug2": "b", "patient": {"pgx": {"CYP2C9": "UM"}}})
    bad_egfr = client.post("/api/predict", json={"drug1": "a", "drug2": "b", "patient": {"egfr": -1}})
    assert bad_gene.status_code == bad_pheno.status_code == bad_egfr.status_code == 422


def test_api_regimen_with_patient():
    # Fluconazole is a strong CYP2C19 inhibitor (omeprazole is only weak in the FDA table and does not phenoconvert)
    body = client.post("/api/regimen", json={"drugs": ["Clopidogrel", "Fluconazole", "Zolpidem"],
                                             "patient": {"age": 80, "pgx": {"CYP2C19": "IM"}}}).json()
    assert body["burden"] is not None
    assert any(a["category"] == "drug-drug-gene" and a["drug"] == "Clopidogrel" for a in body["patient_alerts"])


def test_weak_inhibitor_does_not_phenoconvert():
    r = analyze_regimen(["Clopidogrel", "Omeprazole"], Patient(pgx={"CYP2C19": "NM"}))
    assert r["phenotypes"]["CYP2C19"]["phenoconverted"] is False
