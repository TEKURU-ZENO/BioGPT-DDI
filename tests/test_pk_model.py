import pytest

from api.ddi import pk_model
from api.ddi.engine import analyze_pair


@pytest.mark.parametrize("strength,sens,lo,hi", [
    ("strong", "sensitive", 5.0, 5.6),     # FDA: strong + sensitive >= 5-fold
    ("strong", "moderate", 2.0, 5.0),      # moderate substrate: 2- to <5-fold
    ("moderate", "sensitive", 2.0, 5.0),   # moderate inhibitor: 2- to <5-fold
    ("weak", "sensitive", 1.25, 2.0),      # weak inhibitor: 1.25- to <2-fold
])
def test_inhibition_point_estimates_match_fda_categories(strength, sens, lo, hi):
    est = pk_model.estimate("inhibit", "CYP3A4", strength, sens)
    assert lo <= est["auc_ratio"] < hi
    assert est["auc_ratio_range"][0] <= est["auc_ratio"] <= est["auc_ratio_range"][1]


def test_strong_induction_of_sensitive_substrate_is_at_least_80_percent_decrease():
    est = pk_model.estimate("induce", "CYP3A4", "strong", "sensitive")
    assert est["auc_ratio"] <= 0.2


def test_transporters_are_not_modelled():
    assert pk_model.estimate("inhibit", "P-gp", "moderate", "sensitive") is None


def test_engine_attaches_estimate_to_mechanism_findings():
    f = analyze_pair("Ketoconazole", "Midazolam")["findings"][0]
    assert f["pk_estimate"]["auc_ratio"] >= 5
    assert "fold increase" in f["pk_estimate"]["summary"]
