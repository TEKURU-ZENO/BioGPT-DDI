import math

from scripts import evaluate_pk


def rows(*items):
    return [{"victim": v, "perpetrator": p, "observed_aucr": str(o), "source": "test"} for v, p, o in items]


def test_category_boundaries():
    assert evaluate_pk.category(15) == "strong-inhibition"
    assert evaluate_pk.category(3) == "moderate-inhibition"
    assert evaluate_pk.category(1.3) == "weak-inhibition"
    assert evaluate_pk.category(1.0) == "none"
    assert evaluate_pk.category(0.1) == "strong-induction"


def test_metrics_on_known_pairs():
    res = evaluate_pk.evaluate(rows(("midazolam", "ketoconazole", 15.0),      # engine ~5.3 -> under-predicted
                                    ("midazolam", "ketoconazole", 15.0),      # duplicate collapses
                                    ("metoprolol", "paroxetine", 2.4),        # engine ~2.4 -> exact
                                    ("metformin", "atorvastatin", 1.6)))["all"]  # no estimate -> coverage gap
    assert res["pairs"] == 3 and res["scored"] == 2
    assert res["within_2"] == 0.5 and res["under_predicted"] == 1
    assert math.isclose(res["coverage"], 2 / 3)
    assert res["worst"][0][:2] == ("midazolam", "ketoconazole")


def test_curated_pairs_have_estimates():
    res = evaluate_pk.evaluate(rows(("simvastatin", "clarithromycin", 10.0)))["all"]
    assert res["scored"] == 1  # estimate carried onto the curated contraindication finding


def test_holdout_split_is_deterministic_and_partitions():
    r = rows(*[("midazolam", p, 3.0) for p in ("ketoconazole", "itraconazole", "clarithromycin", "erythromycin",
                                               "fluconazole", "diltiazem", "verapamil", "rifampin")])
    a = evaluate_pk.evaluate(r, holdout_seed=1)
    b = evaluate_pk.evaluate(r, holdout_seed=1)
    assert a["calibration"]["pairs"] + a["holdout"]["pairs"] == a["all"]["pairs"] == 8
    assert a["calibration"]["pairs"] == b["calibration"]["pairs"]
