import copy
from pathlib import Path

from api.ddi.lexicon import DRUGS, merge_roles
from scripts.import_fda_cyp_table import clean_names, parse_html

FIX = Path(__file__).parent / "fixtures" / "fda_cyp_table.html"


def test_parse_tables():
    roles = parse_html(FIX.read_text())
    assert roles["midazolam"]["sub"] == {"CYP3A4": "sensitive"}
    assert roles["triazolam"]["sub"] == {"CYP3A4": "sensitive"}          # footnote <sup> ignored
    assert roles["atorvastatin"]["sub"] == {"CYP3A4": "moderate"}        # parenthetical stripped
    assert roles["repaglinide"]["sub"] == {"CYP2C8": "sensitive"}
    assert roles["gemfibrozil"]["inh"] == {"CYP2C8": "strong"}
    assert roles["clopidogrel"]["inh"] == {"CYP2C8": "moderate"}
    assert roles["apalutamide"]["ind"] == {"CYP3A4": "strong"}
    assert roles["modafinil"]["ind"] == {"CYP3A4": "weak"}


def test_clean_names():
    assert clean_names("triazolam, atorvastatin (b); grapefruit juice") == ["triazolam", "atorvastatin",
                                                                             "grapefruit juice"]


def test_merge_never_overwrites_and_records_conflicts():
    drugs = copy.deepcopy(DRUGS)
    data = {"roles": parse_html(FIX.read_text())}
    data["roles"]["verapamil"]["inh"]["CYP3A4"] = "strong"  # disagree with curated "moderate"
    stats = merge_roles(drugs, data)
    assert drugs["verapamil"].inh["CYP3A4"] == "moderate"
    assert {"drug": "verapamil", "role": "inhibitor", "enzyme": "CYP3A4", "lexicon": "moderate",
            "fda_table": "strong"} in stats["conflicts"]
    assert "ibrutinib" in stats["added"] and drugs["ibrutinib"].sub == {"CYP3A4": "sensitive"}
    assert "gemfibrozil" in stats["enriched"] and drugs["gemfibrozil"].inh == {"CYP2C8": "strong"}
    assert "ibrutinib" not in DRUGS  # global lexicon untouched


def test_new_mechanism_only_drug_participates_in_engine(monkeypatch):
    import api.ddi.engine as engine

    drugs = copy.deepcopy(DRUGS)
    merge_roles(drugs, {"roles": parse_html(FIX.read_text())})
    monkeypatch.setattr(engine, "DRUGS", drugs)
    import api.ddi.normalize as normalize
    monkeypatch.setattr(normalize, "DRUGS", drugs)
    r = engine.analyze_pair("Ibrutinib", "Itraconazole")
    assert r["severity"] == "Major"
    assert r["findings"][0]["pk_estimate"]["auc_ratio"] >= 5


def test_title_row_above_header_and_rowspan_enzyme():
    html = """<table>
    <tr><td colspan="4">Table 2-2. Examples of clinical inhibitors for P450-mediated metabolisms</td></tr>
    <tr><th>Enzyme</th><th>Strong inhibitors</th><th>Moderate inhibitors</th><th>Weak inhibitors</th></tr>
    <tr><td rowspan="2">CYP2D6</td><td>bupropion, paroxetine</td><td>duloxetine</td><td>cimetidine</td></tr>
    <tr><td>quinidine</td><td>mirabegron</td><td></td></tr>
    </table>"""
    roles = parse_html(html)
    assert roles["bupropion"]["inh"] == {"CYP2D6": "strong"}
    assert roles["quinidine"]["inh"] == {"CYP2D6": "strong"}       # continuation row of a rowspan
    assert roles["mirabegron"]["inh"] == {"CYP2D6": "moderate"}
    assert roles["cimetidine"]["inh"] == {"CYP2D6": "weak"}
