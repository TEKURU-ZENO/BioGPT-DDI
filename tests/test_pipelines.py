import math
from pathlib import Path

import httpx
import pytest

from pipelines import faers, literature

FIX = Path(__file__).parent / "fixtures"


# ------------------------------------------------------------------ literature
def test_dictionary_ner_longest_match_and_brands():
    m = [x[0] for x in literature.find_drugs("Patients on Coumadin and isosorbide mononitrate took Diflucan.")]
    assert m == ["warfarin", "isosorbide mononitrate", "fluconazole"]


def test_ner_does_not_match_inside_words():
    assert literature.find_drugs("Lithiumcarbonate-free and prewarfarin era") == []


def test_negation_suppresses_score():
    pos, _ = literature.pattern_scorer("Drug A increased the AUC of drug B 3-fold.", "a", "b")
    neg, cues = literature.pattern_scorer("Drug A did not significantly alter the AUC of drug B.", "a", "b")
    assert pos >= 0.5 and neg < 0.5 and "negated" in cues


def test_mining_flags_novel_and_known_pairs():
    abstracts = literature.parse_pubmed_xml((FIX / "pubmed_sample.xml").read_text())
    assert [a.pmid for a in abstracts] == ["11111111", "22222222", "33333333"]
    rows = literature.aggregate(literature.mine(abstracts))
    pairs = {(r["drug1"], r["drug2"]): r for r in rows}
    assert pairs[("Fluvoxamine", "Tizanidine")]["novel"] is False      # already contraindicated in the KB
    assert pairs[("Levetiracetam", "Rosuvastatin")]["novel"] is True   # emerging candidate for review
    assert ("Clopidogrel", "Pantoprazole") not in pairs                # negated sentence filtered
    assert rows[0]["novel"] is True                                     # novel candidates ranked first


# ------------------------------------------------------------------ FAERS
def test_ror_matches_hand_calculation():
    r = faers.ror(faers.Table(a=20, b=80, c=100, d=9800))
    assert math.isclose(r["ror"], (20 / 80) / (100 / 9800))
    assert r["lower95"] < r["ror"] < r["upper95"]


def test_ror_zero_cases_and_haldane():
    assert faers.ror(faers.Table(0, 10, 10, 100)) is None
    assert faers.ror(faers.Table(5, 0, 10, 100))["ror"] > 0


def test_table_from_counts():
    t = faers.table_from_counts(n_total=10000, n_event=120, n_exposed=100, n_exposed_event=20)
    assert (t.a, t.b, t.c, t.d) == (20, 80, 100, 9800)


def test_interaction_signal_requires_combo_to_exceed_components():
    combo = {"ror": 6.0, "lower95": 3.0, "n_cases": 10}
    assert faers.interaction_signal(combo, {"ror": 2.0}, {"ror": 1.5})
    assert not faers.interaction_signal(combo, {"ror": 7.0}, {"ror": 1.5})
    assert not faers.interaction_signal({"ror": 6.0, "lower95": 0.9, "n_cases": 10}, None, None)
    assert not faers.interaction_signal({"ror": 6.0, "lower95": 3.0, "n_cases": 2}, None, None)


def test_screen_with_mocked_openfda(monkeypatch):
    totals = {None: 100000, "EV": 1000, "A": 2000, "B": 1500, "AB": 100,
              "A+EV": 40, "B+EV": 20, "AB+EV": 15}

    def handler(request: httpx.Request):
        q = request.url.params.get("search")
        key = None
        if q:
            has_a, has_b = "WARFARIN" in q, "FLUCONAZOLE" in q
            ev = "reactionmeddrapt" in q
            key = ("AB" if has_a and has_b else "A" if has_a else "B" if has_b else "") + ("+EV" if ev and (has_a or has_b) else "")
            key = key or "EV"
        return httpx.Response(200, json={"meta": {"results": {"total": totals[key]}}})

    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    out = faers.screen("warfarin", "fluconazole", "HAEMORRHAGE")
    assert out["signal"] is True
    assert out["ror"]["combination"]["ror"] > out["ror"]["warfarin"]["ror"]
