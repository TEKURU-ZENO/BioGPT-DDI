import csv
import io

import pytest

from scripts.references import ddinter, kegg, onc, pk_labels, pk_table
from scripts.references.common import write_reference


def _read(path):
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------------ common
def test_write_reference_keeps_highest_grade_per_unordered_pair(tmp_path):
    out = tmp_path / "r.csv"
    n = write_reference([
        {"drug1": "warfarin", "drug2": "aspirin", "severity": "Precaution"},
        {"drug1": "aspirin", "drug2": "warfarin", "severity": "Contraindicated"},
        {"drug1": "aspirin", "drug2": "aspirin", "severity": "Major"},
    ], out)
    rows = _read(out)
    assert n == 1 and rows[0]["severity"] == "Contraindicated"


# ------------------------------------------------------------------ DDInter
DDI_CSV = """DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level
DDInter1,Warfarin,DDInter2,Fluconazole,Major
DDInter3,Sertraline,DDInter4,Ibuprofen,Moderate
DDInter5,Zorbatrol,DDInter1,Warfarin,Major
DDInter6,Metformin,DDInter7,Atorvastatin,Unknown
"""


def test_ddinter_parse_and_lexicon_coverage():
    stats = {}
    rows = ddinter.parse(csv.DictReader(io.StringIO(DDI_CSV)), stats)
    assert {(r["drug1"], r["drug2"], r["severity"]) for r in rows} == {
        ("warfarin", "fluconazole", "Major"), ("sertraline", "ibuprofen", "Moderate"),
        ("metformin", "atorvastatin", "Unknown")}
    assert len(stats["drugs_known"]) == 6 and len(stats["drugs_seen"]) == 7


def test_ddinter_negatives_exclude_listed_pairs(tmp_path):
    src = tmp_path / "d.csv"
    src.write_text(DDI_CSV)
    out = tmp_path / "ref.csv"
    assert ddinter.main([str(src), "--negatives", "5", "--out", str(out)]) == 0
    rows = _read(out)
    neg = {tuple(sorted((r["drug1"], r["drug2"]))) for r in rows if r["severity"] == "None"}
    pos = {tuple(sorted((r["drug1"], r["drug2"]))) for r in rows if r["severity"] != "None"}
    assert neg and not neg & pos


# ------------------------------------------------------------------ KEGG
def test_kegg_find_and_ddi_parsing():
    find = "dr:D08681\tWarfarin potassium (JAN)\ndr:D00564\tWarfarin (USP); Coumadin (TN)\n"
    assert kegg.parse_find(find, "warfarin") == "D08681"  # salt stripped -> matches first
    ddi = "dr:D00564\tdr:D00322\tCI,P\tEnzyme: CYP2C9\ndr:D00564\tdg:DG00123\tP\tclass\ndr:D00564\tdr:D00109\tP\t\n"
    parsed = kegg.parse_ddi(ddi)
    assert [(a, b, sorted(l)) for a, b, l, _ in parsed] == [("D00564", "D00322", ["CI", "P"]),
                                                          ("D00564", "D00109", ["P"])]


# ------------------------------------------------------------------ ONC
def test_onc_requires_transcription(tmp_path):
    t = tmp_path / "t.csv"
    t.write_text("list,object_a,object_b,citation\n")
    assert onc.main(["--transcription", str(t), "--out", str(tmp_path / "o.csv")]) == 1


def test_onc_expands_classes(tmp_path):
    t = tmp_path / "t.csv"
    t.write_text("list,object_a,object_b,citation\nhigh,@maoi,fluoxetine,test\nlow,atorvastatin,unobtainium,test\n")
    out = tmp_path / "o.csv"
    assert onc.main(["--transcription", str(t), "--out", str(out)]) == 0
    rows = _read(out)
    assert {r["severity"] for r in rows} == {"Major"}
    assert any({r["drug1"], r["drug2"]} == {"fluoxetine", "phenelzine"} for r in rows)
    assert not any("atorvastatin" in (r["drug1"], r["drug2"]) for r in rows)  # unmapped entry skipped


# ------------------------------------------------------------------ PK references
@pytest.mark.parametrize("text,label,expected", [
    ("Coadministration with ketoconazole increased the AUC of midazolam 15-fold.", "midazolam",
     ("midazolam", "ketoconazole", 15.0, "explicit")),
    ("Rifampin decreased midazolam AUC by 96%.", "midazolam", ("midazolam", "rifampin", 0.04, "explicit")),
    ("When given with fluconazole, AUC increased by 80%.", "celecoxib", ("celecoxib", "fluconazole", 1.8, "assumed")),
    ("Clarithromycin increased the AUC of digoxin 1.7-fold.", "clarithromycin",
     ("digoxin", "clarithromycin", 1.7, "explicit")),
    ("Rifampin reduced the AUC of tadalafil by 8-fold.", "tadalafil", ("tadalafil", "rifampin", 0.125, "explicit")),
])
def test_label_pk_extraction(text, label, expected):
    rows = pk_labels.extract(text, label)
    assert len(rows) == 1
    r = rows[0]
    assert (r["victim"], r["perpetrator"], r["observed_aucr"], r["direction"]) == expected


def test_label_pk_skips_ambiguous_and_unquantified():
    assert pk_labels.extract("Ketoconazole and itraconazole increased the AUC of midazolam 10-fold.", "midazolam") == []
    assert pk_labels.extract("Ketoconazole increased exposure to midazolam.", "midazolam") == []


def test_pk_table_column_matching(tmp_path):
    rows, skipped = pk_table.convert(
        [{"Substrate": "Midazolam", "Inhibitor": "Itraconazole", "AUC ratio": "10,8", "PMID": "123"},
         {"Substrate": "Zorbatrol", "Inhibitor": "Itraconazole", "AUC ratio": "2", "PMID": "1"}],
        ["Substrate", "Inhibitor", "AUC ratio", "PMID"], "test")
    assert skipped == 1 and rows[0]["observed_aucr"] == 10.8 and rows[0]["source_id"] == "123"
    with pytest.raises(ValueError):
        pk_table.convert([], ["a", "b"], "x")
