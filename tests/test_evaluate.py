import csv

from scripts import evaluate


def test_weighted_kappa_perfect_and_chance():
    assert evaluate.weighted_kappa([0, 1, 2, 3, 4], [0, 1, 2, 3, 4]) == 1.0
    assert evaluate.weighted_kappa([0, 4, 0, 4], [4, 0, 4, 0]) < 0


def test_gold_standard_passes_with_full_critical_recall(tmp_path):
    out = tmp_path / "report.md"
    assert evaluate.main(["--out", str(out)]) == 0
    assert "Safety-critical recall" in out.read_text()


def test_reference_agreement(tmp_path):
    ref = tmp_path / "ref.csv"
    with ref.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["drug1", "drug2", "severity"])
        w.writerows([["Warfarin", "Fluconazole", "Major"], ["Sertraline", "Ibuprofen", "Major"],
                     ["Amoxicillin", "Ibuprofen", "None"]])
    res = evaluate.evaluate_reference(list(csv.DictReader(ref.open())))
    assert res["pairs"] == 3
    assert res["engine_lower_than_reference"] == 1  # SSRI+NSAID graded Moderate by the engine
    assert 0 < res["exact_agreement"] < 1
