import csv
import json
from pathlib import Path

import pytest

from api.ddi import pk_model
from api.ddi.engine import analyze_pair
from scripts import evaluate_pk, fit_pk_params

FIX = Path(__file__).parent / "fixtures" / "pk_crir_fixture.csv"


def _rows():
    with FIX.open(newline="") as fh:
        return list(csv.DictReader(line for line in fh if not line.startswith("#")))


@pytest.fixture
def params_path(tmp_path, monkeypatch):
    path = tmp_path / "pk_crir.json"
    monkeypatch.setenv("DDI_PK_PARAMS", str(path))
    pk_model.reload()
    yield path
    monkeypatch.delenv("DDI_PK_PARAMS")
    pk_model.reload()


def _fit(path, seed):
    src = path.parent / "ref.csv"
    rows = _rows()
    with src.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    assert fit_pk_params.main([str(src), "--holdout-seed", str(seed), "--out", str(path)]) == 0
    pk_model.reload()
    return json.loads(path.read_text())


def test_fit_uses_only_the_calibration_half(params_path):
    params = _fit(params_path, seed=3)
    obs = fit_pk_params.collapse(_rows())
    cal = {k for k in obs if evaluate_pk._split(*k, 3) == "calibration"}
    assert params["pairs"] == len(cal) < len(obs)


def test_very_sensitive_substrate_gets_higher_cr_than_class_prior(params_path):
    params = _fit(params_path, seed=3)
    assert params["cr"]["buspirone"]["CYP3A4"]["value"] > pk_model.FM_SUBSTRATE["sensitive"][1]


def test_engine_uses_fitted_parameters_and_can_disable_them(params_path, monkeypatch):
    before = analyze_pair("Buspirone", "Itraconazole")["findings"][0]["pk_estimate"]
    _fit(params_path, seed=3)
    after = analyze_pair("Buspirone", "Itraconazole")["findings"][0]["pk_estimate"]
    assert after["model"] == pk_model.FITTED_MODEL_NAME and after["auc_ratio"] > before["auc_ratio"]
    assert after["auc_ratio_range"][0] <= after["auc_ratio"] <= after["auc_ratio_range"][1]
    monkeypatch.setenv("DDI_DISABLE_PK_FIT", "1")
    pk_model.reload()
    assert analyze_pair("Buspirone", "Itraconazole")["findings"][0]["pk_estimate"]["model"] == pk_model.MODEL_NAME


def test_fitting_improves_holdout_error(params_path, monkeypatch):
    monkeypatch.setenv("DDI_DISABLE_PK_FIT", "1")
    pk_model.reload()
    base = evaluate_pk.evaluate(_rows(), holdout_seed=3)["holdout"]["gmfe"]
    monkeypatch.delenv("DDI_DISABLE_PK_FIT")
    _fit(params_path, seed=3)
    fitted = evaluate_pk.evaluate(_rows(), holdout_seed=3)["holdout"]["gmfe"]
    assert fitted < base
