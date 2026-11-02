"""Optional learned-model signal (Phase 3 layer C).

If ``DDI_MODEL_PATH`` points to an artifact exported by
``research/ddi_ml/train.py`` (and numpy, scikit-learn and joblib are
installed), pairs that the curated, mechanism and external layers found
nothing for are scored. Only a conformal singleton-positive prediction is
reported, as ``predicted_signal``. It never assigns, raises or lowers a
severity.

Security: joblib artifacts are pickles. Load only artifacts you built; the
path is operator configuration, never user input.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger("biogpt_ddi.learned")


@lru_cache(maxsize=1)
def _artifact():
    path = os.getenv("DDI_MODEL_PATH")
    if not path or not os.path.exists(path):
        return None
    try:
        import joblib

        art = joblib.load(path)
        if art.get("artifact_version") != 1:
            logger.warning("unsupported model artifact version %s", art.get("artifact_version"))
            return None
        return art
    except Exception:
        logger.exception("could not load learned model from %s", path)
        return None


def reload() -> None:
    _artifact.cache_clear()


def status() -> dict:
    art = _artifact()
    if not art:
        return {"loaded": False}
    m = art["metrics"]
    return {"loaded": True, "created": art["created"], "split": m["split"], "auroc": m["auroc"],
            "alpha": art["alpha"], "ingredients": len(art["fingerprints"])}


def predict(a: str, b: str) -> Optional[dict]:
    art = _artifact()
    if not art:
        return None
    fa, fb = art["fingerprints"].get(a), art["fingerprints"].get(b)
    if fa is None or fb is None:
        return None
    import numpy as np

    x = np.concatenate([fa + fb, fa * fb]).astype(np.float32)[None, :]
    p = float(art["model"].predict_proba(x)[0, 1])
    qhat = art["qhat"]
    in_set = {y for y, ok in ((1, 1 - p <= qhat), (0, p <= qhat)) if ok}
    if in_set != {1}:
        return None
    m = art["metrics"]
    return {
        "label": "Possible interaction - predicted, not documented",
        "probability": round(p, 3),
        "conformal_confidence": round(1 - art["alpha"], 3),
        "model": f"Fingerprint model ({m['fingerprint']}), {m['split']} split, AUROC {m['auroc']}",
        "note": "Statistical signal from chemical structure only. No severity is assigned; verify in a clinical "
                "reference before acting.",
    }
