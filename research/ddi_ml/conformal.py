"""Split-conformal prediction for binary classification.

Nonconformity score s = 1 - p(true class) (the "LAC" score). With a held-out
calibration set of n examples, the threshold

    q = the ceil((n + 1)(1 - alpha)) / n quantile of calibration scores

gives prediction sets C(x) = {y : 1 - p(y|x) <= q} that contain the true label
with probability >= 1 - alpha, assuming exchangeability between calibration
and test data. Drug-level splits break exchangeability with random-split
calibration, so calibrate on data drawn the same way as the deployment
setting (the training script calibrates within the chosen split).

Only a singleton set {1} is surfaced by the API as a predicted signal; {0, 1}
means "the model cannot tell at this confidence level".
"""

from __future__ import annotations

from typing import List

import numpy as np


def calibrate(p_pos: np.ndarray, y: np.ndarray, alpha: float = 0.1) -> float:
    p_true = np.where(y == 1, p_pos, 1 - p_pos)
    scores = 1 - p_true
    n = len(scores)
    if n == 0:
        raise ValueError("empty calibration set")
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores, level, method="higher"))


def prediction_sets(p_pos: np.ndarray, qhat: float) -> List[set]:
    out = []
    for p in p_pos:
        s = set()
        if 1 - p <= qhat:
            s.add(1)
        if p <= qhat:  # 1 - (1 - p)
            s.add(0)
        out.append(s)
    return out


def summarize(sets: List[set], y: np.ndarray) -> dict:
    covered = np.mean([int(t) in s for s, t in zip(sets, y)]) if len(y) else float("nan")
    sizes = np.array([len(s) for s in sets])
    return {
        "coverage": float(covered),
        "mean_set_size": float(sizes.mean()) if len(sizes) else float("nan"),
        "singleton_positive_rate": float(np.mean([s == {1} for s in sets])) if sets else float("nan"),
        "empty_rate": float(np.mean(sizes == 0)) if len(sizes) else float("nan"),
    }
