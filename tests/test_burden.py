from api.ddi.engine import analyze_regimen
from api.ddi.patient import Patient


def axes(r):
    return {a["axis"]: a for a in r["burden"]["alerts"]}


def test_anticholinergic_burden_sums():
    r = analyze_regimen(["Amitriptyline", "Diphenhydramine", "Metoprolol"])
    assert r["burden"]["anticholinergic"]["total"] == 7
    assert "anticholinergic" in axes(r)


def test_beers_cns_alert_is_critical_for_older_adults():
    meds = ["Sertraline", "Zolpidem", "Gabapentin"]
    assert axes(analyze_regimen(meds))["cns"]["level"] == "warning"
    assert axes(analyze_regimen(meds, Patient(age=78)))["cns"]["level"] == "critical"


def test_qt_burden():
    r = analyze_regimen(["Citalopram", "Ondansetron", "Azithromycin"])
    assert axes(r)["qt"]["level"] == "critical"


def test_combination_products_are_counted_once():
    r = analyze_regimen(["Percocet", "Tylenol"])
    assert r["highest_severity"] == "Major"  # acetaminophen duplication


def test_clean_regimen_has_no_alerts():
    r = analyze_regimen(["Metformin", "Atorvastatin", "Lisinopril"])
    assert r["burden"]["alerts"] == []
