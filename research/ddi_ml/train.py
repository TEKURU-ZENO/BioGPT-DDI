"""Train, calibrate, evaluate and export a learned DDI model.

Example (TDC DrugBank, binary interaction task with sampled negatives)::

    python -m research.ddi_ml.train data/drugbank.csv --split cold_drug \
        --names data/drugbank_names.csv --out models/ddi_model.joblib

``--names`` is an optional CSV with columns ``Drug_ID,Name`` (e.g. from the
CC0 DrugBank vocabulary) used to map training drugs to this project's
ingredient names so the API can look them up.

Outputs ``<out>`` (joblib artifact), ``<out>.metrics.json`` and
``<out>.model_card.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from . import conformal
from .data import PairDataset, load_csv, sample_negatives
from .features import HAVE_RDKIT, fingerprint, featurize
from .splits import check_no_leakage, split

ARTIFACT_VERSION = 1


def _model(seed: int):
    return LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced", random_state=seed)


def run(ds: PairDataset, mode: str = "cold_drug", alpha: float = 0.1, seed: int = 0,
        fp_method: str = "auto") -> dict:
    s = split(ds, mode, seed=seed)
    leaks, n_test = check_no_leakage(ds, s, mode)
    if leaks:
        raise RuntimeError(f"split leakage: {leaks}/{n_test} test pairs violate the {mode} setting")
    parts = {k: ds.subset(v) for k, v in s.items()}
    X = {k: featurize(p.a, p.b, ds.smiles, fp_method) for k, p in parts.items()}
    y = {k: p.y for k, p in parts.items()}
    if len(set(y["train"])) < 2:
        raise RuntimeError("training split has a single class; add negatives (--neg-ratio)")

    model = _model(seed).fit(X["train"], y["train"])
    p_cal = model.predict_proba(X["cal"])[:, 1]
    qhat = conformal.calibrate(p_cal, y["cal"], alpha)
    p_test = model.predict_proba(X["test"])[:, 1]
    sets = conformal.prediction_sets(p_test, qhat)

    two_class = len(set(y["test"])) == 2
    metrics = {
        "split": mode, "alpha": alpha, "seed": seed,
        "n": {k: len(v) for k, v in s.items()},
        "auroc": float(roc_auc_score(y["test"], p_test)) if two_class else None,
        "auprc": float(average_precision_score(y["test"], p_test)) if two_class else None,
        "positive_rate_test": float(np.mean(y["test"])) if len(y["test"]) else None,
        "conformal": conformal.summarize(sets, y["test"]),
        "fingerprint": "morgan-r2-1024" if (HAVE_RDKIT and fp_method != "ngram") else "smiles-ngram-1024",
    }
    return {"model": model, "qhat": qhat, "metrics": metrics}


def export(result: dict, ds: PairDataset, out: Path, ingredient_of: Dict[str, str], fp_method: str) -> dict:
    import joblib

    fps = {}
    for drug_id, ing in ingredient_of.items():
        if drug_id in ds.smiles:
            fps[ing] = fingerprint(ds.smiles[drug_id], fp_method).astype(np.uint8)
    artifact = {
        "artifact_version": ARTIFACT_VERSION,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": result["model"], "qhat": result["qhat"], "alpha": result["metrics"]["alpha"],
        "fp_method": fp_method, "fingerprints": fps, "metrics": result["metrics"],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, out)
    Path(f"{out}.metrics.json").write_text(json.dumps(result["metrics"], indent=2))
    Path(f"{out}.model_card.md").write_text(model_card(result["metrics"], len(fps)))
    return artifact


def model_card(m: dict, n_mapped: int) -> str:
    c = m["conformal"]
    return f"""# Learned DDI model card

- **Task:** binary "does this pair interact?" using Morgan fingerprints and logistic regression
- **Split:** `{m['split']}` (train/cal/test pairs: {m['n']['train']}/{m['n']['cal']}/{m['n']['test']})
- **Fingerprint:** {m['fingerprint']}
- **AUROC:** {m['auroc']}  **AUPRC:** {m['auprc']} (test positive rate {m['positive_rate_test']})
- **Conformal (alpha={m['alpha']}):** coverage {c['coverage']:.3f}, mean set size {c['mean_set_size']:.2f},
  singleton-positive rate {c['singleton_positive_rate']:.3f}
- **Ingredients mapped for API lookup:** {n_mapped}

## Intended use
Research signal for drug pairs that the curated and mechanism layers do not cover. The API surfaces only
conformal singleton-positive predictions, labelled "predicted - not documented", and never assigns, raises or
lowers a severity.

## Known limitations
- Negatives are sampled unobserved pairs: some are unrecognised true interactions.
- Structure-only features ignore dose, route, indication and patient factors.
- Conformal guarantees assume calibration and deployment data are exchangeable.
"""


def _read_names(path: Optional[Path]) -> Dict[str, str]:
    if not path:
        return {}
    os.environ.setdefault("DDI_ENABLE_RXNAV", "false")
    from api.ddi.normalize import resolve

    out = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            r = resolve(row["Name"])
            if r.recognized and len(r.ingredients) == 1:
                out[row["Drug_ID"]] = r.ingredients[0]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--split", choices=["random", "cold_drug", "cold_both"], default="cold_drug")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--neg-ratio", type=float, default=1.0, help="sampled negatives per positive (0 = none)")
    ap.add_argument("--names", type=Path)
    ap.add_argument("--fp", choices=["auto", "morgan", "ngram"], default="auto")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("models/ddi_model.joblib"))
    args = ap.parse_args(argv)

    ds = load_csv(args.csv)
    if args.neg_ratio > 0:
        ds = sample_negatives(ds, args.neg_ratio, args.seed)
    result = run(ds, args.split, args.alpha, args.seed, args.fp)
    export(result, ds, args.out, _read_names(args.names), args.fp)
    print(json.dumps(result["metrics"], indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
