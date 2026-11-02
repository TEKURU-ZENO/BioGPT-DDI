"""Learned-layer pipeline on a synthetic dataset with a known structural rule.

A pair interacts iff one drug carries a primary amine and the other a chloride.
Because the rule is structural, a fingerprint model should generalise to
unseen drugs, which is exactly what the cold splits test.
"""

import csv
import itertools

import numpy as np
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("joblib")

from api.ddi import learned  # noqa: E402
from api.ddi.engine import analyze_pair  # noqa: E402
from research.ddi_ml import conformal  # noqa: E402
from research.ddi_ml.data import PairDataset, sample_negatives  # noqa: E402
from research.ddi_ml.features import featurize  # noqa: E402
from research.ddi_ml.splits import check_no_leakage, split  # noqa: E402
from research.ddi_ml.train import main, run  # noqa: E402


def _drugs():
    out = {}
    for n in range(2, 12):
        chain = "C" * n
        out[f"AM{n}"] = f"N{chain}"          # amine
        out[f"CL{n}"] = f"Cl{chain}"         # chloride
        out[f"OH{n}"] = f"O{chain}"          # alcohol
        out[f"ET{n}"] = f"{chain}OC"         # ether
    return out


def _dataset() -> PairDataset:
    smiles = _drugs()
    a, b, y = [], [], []
    for x, z in itertools.combinations(sorted(smiles), 2):
        kinds = {x[:2], z[:2]}
        a.append(x)
        b.append(z)
        y.append(int(kinds == {"AM", "CL"}))
    return PairDataset(a, b, np.array(y), smiles, {})


def test_features_are_order_invariant():
    ds = _dataset()
    assert np.array_equal(featurize(["AM3"], ["CL4"], ds.smiles), featurize(["CL4"], ["AM3"], ds.smiles))


@pytest.mark.parametrize("mode", ["random", "cold_drug", "cold_both"])
def test_splits_have_no_leakage(mode):
    ds = _dataset()
    s = split(ds, mode, seed=1)
    assert s["test"] and s["train"] and s["cal"]
    assert not set(s["train"]) & set(s["test"])
    if mode != "random":
        assert check_no_leakage(ds, s, mode)[0] == 0


def test_unknown_split_rejected():
    with pytest.raises(ValueError):
        split(_dataset(), "nonsense")


def test_conformal_coverage_on_exchangeable_data():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 4000)
    p = np.clip(np.where(y == 1, 0.7, 0.3) + rng.normal(0, 0.2, 4000), 0.01, 0.99)
    q = conformal.calibrate(p[:2000], y[:2000], alpha=0.1)
    summary = conformal.summarize(conformal.prediction_sets(p[2000:], q), y[2000:])
    assert summary["coverage"] >= 0.88


def test_model_generalises_to_unseen_drugs():
    m = run(_dataset(), "cold_drug", alpha=0.1, seed=0)["metrics"]
    assert m["auroc"] > 0.9
    assert m["conformal"]["coverage"] >= 0.8


def test_negative_sampling_adds_only_unobserved_pairs():
    pos = PairDataset(["A", "B"], ["B", "C"], np.array([1, 1]), {k: "C" for k in "ABCD"}, {})
    ds = sample_negatives(pos, ratio=1.0, seed=0)
    neg = {tuple(sorted(p)) for p, t in zip(zip(ds.a, ds.b), ds.y) if t == 0}
    assert neg and not neg & {("A", "B"), ("B", "C")}


def test_cli_and_api_signal(tmp_path, monkeypatch):
    ds = _dataset()
    data = tmp_path / "pairs.csv"
    with data.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Drug1_ID", "Drug1", "Drug2_ID", "Drug2", "Y"])
        for x, z, t in zip(ds.a, ds.b, ds.y):
            w.writerow([x, ds.smiles[x], z, ds.smiles[z], t])
    # Map two synthetic drugs onto real ingredients with no known interaction in the KB
    names = tmp_path / "names.csv"
    names.write_text("Drug_ID,Name\nAM5,Metformin\nCL6,Atorvastatin\nOH3,Levothyroxine\n")
    out = tmp_path / "model.joblib"
    assert main([str(data), "--neg-ratio", "0", "--names", str(names), "--out", str(out)]) == 0
    assert out.exists() and (tmp_path / "model.joblib.model_card.md").exists()

    assert "predicted_signals" not in analyze_pair("Metformin", "Atorvastatin")  # no model configured
    monkeypatch.setenv("DDI_MODEL_PATH", str(out))
    learned.reload()
    try:
        r = analyze_pair("Metformin", "Atorvastatin")
        assert r["severity"] == "None known"  # never assigns severity
        sig = r["predicted_signals"][0]
        assert sig["label"].startswith("Possible interaction - predicted")
        assert "predicted_signals" not in analyze_pair("Metformin", "Levothyroxine")  # amine + alcohol
        # documented interactions are untouched by the model
        assert analyze_pair("Warfarin", "Fluconazole")["severity"] == "Major"
        assert learned.status()["loaded"] is True
    finally:
        monkeypatch.delenv("DDI_MODEL_PATH")
        learned.reload()
