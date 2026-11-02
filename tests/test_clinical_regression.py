"""Clinical regression gold set.

Each case encodes the expected *minimum* severity for a well-documented
interaction (or the expected non-interaction outcome). The first block holds
cases the original rule-based classifier got dangerously wrong.
"""

import pytest

from api.ddi.engine import SEVERITY_RANK, analyze_pair

AT_LEAST = [
    # --- regressions from v1 (previously Minor / Moderate) ---
    ("Warfarin", "Fluconazole", "Major"),
    ("Linezolid", "Sertraline", "Contraindicated"),
    ("Tramadol", "Sertraline", "Major"),
    ("Fluoxetine", "Tramadol", "Major"),
    ("Clopidogrel", "Omeprazole", "Major"),
    ("Coumadin", "Aspirin", "Major"),
    # --- contraindicated ---
    ("Sildenafil", "Nitroglycerin", "Contraindicated"),
    ("Viagra", "Isosorbide mononitrate", "Contraindicated"),
    ("Tadalafil", "Riociguat", "Contraindicated"),
    ("Simvastatin", "Clarithromycin", "Contraindicated"),
    ("Lovastatin", "Itraconazole", "Contraindicated"),
    ("Simvastatin", "Gemfibrozil", "Contraindicated"),
    ("Phenelzine", "Fluoxetine", "Contraindicated"),
    ("Selegiline", "Meperidine", "Contraindicated"),
    ("Tizanidine", "Ciprofloxacin", "Contraindicated"),
    ("Tizanidine", "Fluvoxamine", "Contraindicated"),
    ("Entresto", "Lisinopril", "Contraindicated"),
    ("Repaglinide", "Gemfibrozil", "Contraindicated"),
    ("Bupropion", "Phenelzine", "Contraindicated"),
    # --- major ---
    ("Warfarin", "Ibuprofen", "Major"),
    ("Warfarin", "Metronidazole", "Major"),
    ("Warfarin", "Bactrim", "Major"),
    ("Warfarin", "Amiodarone", "Major"),
    ("Warfarin", "Rifampin", "Major"),
    ("Apixaban", "Ketoconazole", "Major"),
    ("Rivaroxaban", "Rifampin", "Major"),
    ("Apixaban", "Aspirin", "Major"),
    ("Oxycodone", "Alprazolam", "Major"),
    ("Morphine", "Gabapentin", "Major"),
    ("Fentanyl", "Alcohol", "Major"),
    ("Lorazepam", "Alcohol", "Major"),
    ("Metoprolol", "Verapamil", "Major"),
    ("Digoxin", "Amiodarone", "Major"),
    ("Digoxin", "Verapamil", "Major"),
    ("Lithium", "Hydrochlorothiazide", "Major"),
    ("Lithium", "Ibuprofen", "Major"),
    ("Lithium", "Lisinopril", "Major"),
    ("Spironolactone", "Potassium chloride", "Major"),
    ("Lisinopril", "Losartan", "Major"),
    ("Theophylline", "Ciprofloxacin", "Major"),
    ("Clozapine", "Fluvoxamine", "Major"),
    ("Tacrolimus", "Ketoconazole", "Major"),
    ("Tacrolimus", "Rifampin", "Major"),
    ("Cyclosporine", "St John's Wort", "Major"),
    ("Colchicine", "Clarithromycin", "Major"),
    ("Methotrexate", "Trimethoprim", "Major"),
    ("Azathioprine", "Allopurinol", "Major"),
    ("Lamotrigine", "Valproate", "Major"),
    ("Tamoxifen", "Paroxetine", "Major"),
    ("Azithromycin", "Amiodarone", "Major"),
    ("Citalopram", "Ondansetron", "Major"),
    ("Metronidazole", "Alcohol", "Major"),
    ("Birth control pill", "Rifampin", "Major"),
    ("Carbamazepine", "Verapamil", "Major"),
    ("Tylenol", "Percocet", "Major"),
    # --- moderate ---
    ("Sertraline", "Ibuprofen", "Moderate"),
    ("Aspirin", "Clopidogrel", "Moderate"),
    ("Lisinopril", "Ibuprofen", "Moderate"),
    ("Lisinopril", "Spironolactone", "Moderate"),
    ("Ciprofloxacin", "Calcium carbonate", "Moderate"),
    ("Levothyroxine", "Iron", "Moderate"),
    ("Simvastatin", "Amlodipine", "Moderate"),
    ("Simvastatin", "Diltiazem", "Moderate"),
    ("Sumatriptan", "Sertraline", "Moderate"),
    ("Glipizide", "Alcohol", "Moderate"),
    ("Metformin", "Alcohol", "Moderate"),
    ("Codeine", "Paroxetine", "Moderate"),
    ("Sildenafil", "Doxazosin", "Moderate"),
]

NONE_KNOWN = [
    ("Amoxicillin", "Ibuprofen"),
    ("Pantoprazole", "Clopidogrel"),
    ("Metformin", "Atorvastatin"),
    ("Levothyroxine", "Atorvastatin"),
    ("Acetaminophen", "Ascorbic acid"),
]

UNRECOGNIZED = [("Water", "Sugar"), ("a", "b"), ("in", "a"), ("Warfrin", "Aspirin"), ("xyzzy", "Warfarin")]


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
