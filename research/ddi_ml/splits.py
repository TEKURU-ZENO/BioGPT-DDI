"""Leakage-aware splits.

Random pair splits put the same drugs in train and test, so a model can score
well by memorising per-drug interaction propensity. Drug-level splits measure
generalisation to new drugs, which is the case that matters for a tool meant to
cover pairs absent from curated databases:

* ``random``    - pairs shuffled (optimistic baseline)
* ``cold_drug`` - test pairs contain exactly one drug unseen in training (S1)
* ``cold_both`` - test pairs contain two unseen drugs (S2, hardest)
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .data import PairDataset


def split(ds: PairDataset, mode: str = "cold_drug", test_frac: float = 0.2, cal_frac: float = 0.1,
          seed: int = 0) -> Dict[str, List[int]]:
    rng = np.random.default_rng(seed)
    n = len(ds)
    if mode == "random":
        idx = rng.permutation(n)
        n_test, n_cal = int(n * test_frac), int(n * cal_frac)
        return {"test": idx[:n_test].tolist(), "cal": idx[n_test:n_test + n_cal].tolist(),
                "train": idx[n_test + n_cal:].tolist()}

    if mode not in ("cold_drug", "cold_both"):
        raise ValueError(f"unknown split mode {mode!r}")
    drugs = np.array(ds.drugs)
    rng.shuffle(drugs)
    k = max(1, int(len(drugs) * (test_frac if mode == "cold_drug" else np.sqrt(test_frac))))
    held = set(drugs[:k].tolist())
    train, test = [], []
    for i, (a, b) in enumerate(zip(ds.a, ds.b)):
        unseen = (a in held) + (b in held)
        if unseen == 0:
            train.append(i)
        elif (mode == "cold_drug" and unseen == 1) or (mode == "cold_both" and unseen == 2):
            test.append(i)
        # pairs that do not fit the setting are dropped to avoid leakage
    train = rng.permutation(train).tolist()
    n_cal = int(len(train) * cal_frac / (1 - test_frac))
    return {"train": train[n_cal:], "cal": train[:n_cal], "test": test}


def check_no_leakage(ds: PairDataset, s: Dict[str, List[int]], mode: str) -> Tuple[int, int]:
    """Return (#test drugs seen in train, #test pairs). Must be 0 seen for cold_both."""
    train_drugs = {d for i in s["train"] for d in (ds.a[i], ds.b[i])}
    seen = 0
    for i in s["test"]:
        both = (ds.a[i] in train_drugs) + (ds.b[i] in train_drugs)
        if mode == "cold_both" and both > 0:
            seen += 1
        if mode == "cold_drug" and both != 1:
            seen += 1
    return seen, len(s["test"])
