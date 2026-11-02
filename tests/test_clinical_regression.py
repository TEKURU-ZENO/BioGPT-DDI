"""Clinical regression gold set.

Cases live in ``eval/gold_standard.csv`` (shared with ``scripts/evaluate.py``).
Each encodes the expected *minimum* severity for a well-documented interaction,
or the expected non-interaction / unrecognised-input outcome. The first rows
are cases the original rule-based classifier got dangerously wrong.
"""

import csv
from pathlib import Path

import pytest

from api.ddi.engine import SEVERITY_RANK, analyze_pair

GOLD = Path(__file__).resolve().parents[1] / "eval" / "gold_standard.csv"
with GOLD.open(newline="", encoding="utf-8") as _fh:
    _ROWS = list(csv.DictReader(_fh))

AT_LEAST = [(r["drug1"], r["drug2"], r["min_severity"]) for r in _ROWS if r["expected"] == "interaction"]
NONE_KNOWN = [(r["drug1"], r["drug2"]) for r in _ROWS if r["expected"] == "none_known"]
UNRECOGNIZED = [(r["drug1"], r["drug2"]) for r in _ROWS if r["expected"] == "unrecognized"]


def test_gold_standard_is_loaded():
    assert len(AT_LEAST) >= 60 and NONE_KNOWN and UNRECOGNIZED


@pytest.mark.parametrize("a,b,minimum", AT_LEAST)
def test_minimum_severity(a, b, minimum):
    r = analyze_pair(a, b)
    assert r["status"] == "interaction_found", r
    assert SEVERITY_RANK[r["severity"]] >= SEVERITY_RANK[minimum], (a, b, r["severity"])
    assert r["findings"] and all(f["evidence"] or f["basis"] == "duplication" for f in r["findings"])


@pytest.mark.parametrize("a,b,minimum", AT_LEAST)
def test_symmetry(a, b, minimum):
    assert analyze_pair(a, b)["severity"] == analyze_pair(b, a)["severity"]


@pytest.mark.parametrize("a,b", NONE_KNOWN)
def test_no_known_interaction(a, b):
    r = analyze_pair(a, b)
    assert r["status"] == "no_known_interaction"
    assert r["severity"] == "None known"


@pytest.mark.parametrize("a,b", UNRECOGNIZED)
def test_unknown_input_is_never_given_a_severity(a, b):
    r = analyze_pair(a, b)
    assert r["status"] == "unrecognized_drug"
    assert r["severity"] == "Unknown"
    assert r["findings"] == []


def test_typo_gets_suggestion_not_autocorrect():
    r = analyze_pair("Warfrin", "Aspirin")
    assert r["drug1"]["recognized"] is False
    assert "warfarin" in r["drug1"]["suggestions"]


def test_combination_product_findings_are_not_duplicated():
    titles = [f["title"] for f in analyze_pair("Bactrim", "Methotrexate")["findings"]]
    assert len(titles) == len(set(titles))
