import copy

import pytest

from api.ddi.engine import LABEL_CYP3A, analyze_pair
from api.ddi.lexicon import DRUGS, DrugProfile


@pytest.mark.parametrize("victim,perp,expected", [
    ("Latuda", "Ketoconazole", "Contraindicated"),       # brand name resolves
    ("Lurasidone", "Rifampin", "Contraindicated"),       # strong inducer
    ("Lurasidone", "Diltiazem", "Moderate"),             # moderate inhibitor: dose reduction only
    ("Lomitapide", "Diltiazem", "Contraindicated"),      # contraindicated with moderate inhibitors too
    ("Ivabradine", "Verapamil", "Major"),                # avoid with moderate inhibitors
    ("Suvorexant", "Itraconazole", "Major"),             # "not recommended"
    ("Tolvaptan", "Rifampin", "Major"),                  # avoid strong inducers
    ("Lurasidone", "Metformin", "None known"),
])
def test_label_restrictions(victim, perp, expected):
    assert analyze_pair(victim, perp)["severity"] == expected


def test_every_tagged_drug_has_a_label_citation():
    tags = ("ci3a_strong_inh", "ci3a_moderate_inh", "avoid3a_strong_inh", "avoid3a_moderate_inh",
            "ci3a_strong_ind", "avoid3a_strong_ind")
    tagged = {n for n, d in DRUGS.items() if any(d.has(t) for t in tags)}
    assert tagged and tagged <= set(LABEL_CYP3A)


def test_rule_applies_to_new_perpetrators_by_role(monkeypatch):
    # A strong CYP3A inhibitor added later (e.g. from the FDA table) triggers the label rule without a name list.
    import api.ddi.engine as engine
    import api.ddi.normalize as normalize

    drugs = copy.deepcopy(DRUGS)
    drugs["newazole"] = DrugProfile(name="newazole", inh={"CYP3A4": "strong"})
    monkeypatch.setattr(engine, "DRUGS", drugs)
    monkeypatch.setattr(normalize, "DRUGS", drugs)
    r = engine.analyze_pair("Naloxegol", "Newazole")
    assert r["severity"] == "Contraindicated"
    assert "Movantik" in r["findings"][0]["evidence"][0]
