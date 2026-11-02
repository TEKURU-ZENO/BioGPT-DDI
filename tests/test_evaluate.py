import csv
import json

from api.ddi import evidence
from api.ddi.engine import analyze_pair
from scripts import evaluate


def test_weighted_kappa_perfect_and_chance():
    assert evaluate.weighted_kappa([0, 1, 2, 3, 4], [0, 1, 2, 3, 4]) == 1.0
    assert evaluate.weighted_kappa([0, 4, 0, 4], [4, 0, 4, 0]) < 0


def test_bootstrap_ci_brackets_estimate():
    items = [1.0] * 80 + [0.0] * 20
    lo, hi = evaluate.bootstrap_ci(items, evaluate._mean)
    assert lo <= 0.8 <= hi and hi - lo < 0.3


def test_gold_standard_passes_with_full_critical_recall(tmp_path):
    out = tmp_path / "report.md"
    assert evaluate.main(["--out", str(out)]) == 0
    assert "Safety-critical recall" in out.read_text()


def _rows(*triples):
    return [{"drug1": a, "drug2": b, "severity": s, "source": "test"} for a, b, s in triples]


def test_ddinter_scale_harmonises_contraindicated_to_major():
    rows = _rows(("Simvastatin", "Clarithromycin", "Major"), ("Warfarin", "Fluconazole", "Major"))
    r = evaluate.evaluate_reference(rows)
    assert r["scale"] == "ddinter"
    assert r["exact_agreement"] == 1.0  # engine Contraindicated counts as Major on this scale
    assert r["by_level"]["Major"]["at_or_above"] == 1.0


def test_reference_metrics_and_negatives():
    rows = _rows(("Warfarin", "Fluconazole", "Major"), ("Sertraline", "Ibuprofen", "Major"),
                 ("Amoxicillin", "Metformin", "Moderate"), ("Amoxicillin", "Ibuprofen", "None"))
    r = evaluate.evaluate_reference(rows)
    assert r["coverage"] == 2 / 3
    assert r["under_calls"] == 2           # SSRI+NSAID graded Moderate; amoxicillin+metformin not found
    assert r["gross_under_calls"] == 1     # Moderate vs None is 2 grades
    assert r["false_alert_rate"] == 0.0 and r["negatives"] == 1


def test_kegg_scale():
    rows = _rows(("Simvastatin", "Clarithromycin", "Contraindicated"), ("Warfarin", "Aspirin", "Precaution"))
    r = evaluate.evaluate_reference(rows)
    assert r["scale"] == "kegg"
    assert r["by_level"]["Contraindicated"]["engine_contraindicated"] == 1.0
    assert r["by_level"]["Precaution"]["detected"] == 1.0


def test_evaluation_disables_external_layer(tmp_path, monkeypatch):
    # With DDInter loaded as an evidence layer, amoxicillin+warfarin would be "found" from DDInter itself.
    (tmp_path / "external_ddi.json").write_text(json.dumps(
        {"source": "DDInter 2.0", "pairs": {"amoxicillin|warfarin": {"level": "Moderate"}}}))
    monkeypatch.setenv("DDI_DATA_DIR", str(tmp_path))
    evidence.reload()
    try:
        assert analyze_pair("Amoxicillin", "Warfarin")["status"] == "interaction_found"
        with evaluate.isolated_engine():
            assert analyze_pair("Amoxicillin", "Warfarin")["status"] == "no_known_interaction"
        assert analyze_pair("Amoxicillin", "Warfarin")["status"] == "interaction_found"  # restored
    finally:
        monkeypatch.delenv("DDI_DATA_DIR")
        evidence.reload()


def test_report_renders_reference_section(tmp_path):
    ref = tmp_path / "ddinter.csv"
    with ref.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["drug1", "drug2", "severity", "source"])
        w.writeheader()
        w.writerows(_rows(("Warfarin", "Fluconazole", "Major"), ("Amoxicillin", "Metformin", "Moderate")))
    out = tmp_path / "r.md"
    assert evaluate.main(["--reference", str(ref), "--out", str(out)]) == 0
    text = out.read_text()
    assert "Independent reference: ddinter" in text and "Coverage" in text
    assert "Gross under-calls (first 25): Amoxicillin + Metformin (ref Moderate, engine None known)" in text


def test_kappa_undefined_for_single_grade_reference():
    rows = _rows(("Simvastatin", "Clarithromycin", "Contraindicated"), ("Warfarin", "Fluconazole", "Contraindicated"))
    r = evaluate.evaluate_reference(rows)
    assert r["weighted_kappa"] != r["weighted_kappa"]  # NaN, reported as n/a
    assert "n/a (reference has a single grade)" in evaluate.report(
        evaluate.evaluate_gold([]), {"kegg": r})


def test_coverage_excluding_unknown_grade():
    rows = _rows(("Warfarin", "Fluconazole", "Major"), ("Amoxicillin", "Metformin", "Unknown"))
    r = evaluate.evaluate_reference(rows)
    assert r["coverage"] == 0.5 and r["coverage_graded"] == 1.0


def test_curation_worklist_counts_undergraded_high_severity_drugs():
    rows = _rows(("Sertraline", "Ibuprofen", "Major"), ("Sertraline", "Aspirin", "Major"),
                 ("Warfarin", "Fluconazole", "Major"))
    r = evaluate.evaluate_reference(rows)
    assert len(r["undergraded_high"]) == 2           # SSRI pairs graded Moderate
    assert r["undergraded_by_drug"][0] == ("Sertraline", 2)
