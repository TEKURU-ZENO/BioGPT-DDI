"""Dataset loading.

Expected CSV columns (TDC ``DrugBank``/``TWOSIDES`` exports use these names)::

    Drug1_ID, Drug1, Drug2_ID, Drug2, Y

``Drug1``/``Drug2`` are SMILES. ``Y`` is an interaction type (DrugBank, 86
classes) or label. TDC DrugBank contains positive pairs only, so the binary
"does this pair interact?" task needs sampled negatives; see
:func:`sample_negatives` and its caveats.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np


@dataclass
class PairDataset:
    a: List[str]            # drug ids
    b: List[str]
    y: np.ndarray           # int labels
    smiles: Dict[str, str]  # drug id -> SMILES
    names: Dict[str, str]   # drug id -> optional display name

    def __len__(self) -> int:
        return len(self.a)

    def subset(self, idx: Sequence[int]) -> "PairDataset":
        idx = list(idx)
        return PairDataset([self.a[i] for i in idx], [self.b[i] for i in idx], self.y[idx], self.smiles, self.names)

    @property
    def drugs(self) -> List[str]:
        return sorted(set(self.a) | set(self.b))


def load_csv(path: Path, binary: bool = True, name_col: str = "") -> PairDataset:
    a, b, y, smiles, names = [], [], [], {}, {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            a.append(row["Drug1_ID"])
            b.append(row["Drug2_ID"])
            smiles[row["Drug1_ID"]] = row["Drug1"]
            smiles[row["Drug2_ID"]] = row["Drug2"]
            if name_col and row.get(f"{name_col}1"):
                names[row["Drug1_ID"]] = row[f"{name_col}1"]
                names[row["Drug2_ID"]] = row[f"{name_col}2"]
            y.append(int(float(row.get("Y", 1))))
    labels = np.array(y, dtype=int)
    if binary:
        labels = (labels > 0).astype(int) if labels.min() == 0 else np.ones_like(labels)
    return PairDataset(a, b, labels, smiles, names)


def sample_negatives(ds: PairDataset, ratio: float = 1.0, seed: int = 0) -> PairDataset:
    """Add random unobserved pairs as negatives.

    Caveat: "not reported" is not "no interaction". Sampled negatives contain
    unknown positives, so measured precision is a lower bound and models can
    learn drug popularity. Report this alongside results.
    """
    rng = np.random.default_rng(seed)
    drugs = ds.drugs
    known = {tuple(sorted(p)) for p in zip(ds.a, ds.b)}
    n_target = int(len(ds) * ratio)
    neg: List[Tuple[str, str]] = []
    seen = set(known)
    attempts = 0
    while len(neg) < n_target and attempts < n_target * 50:
        attempts += 1
        i, j = rng.choice(len(drugs), size=2, replace=False)
        pair = tuple(sorted((drugs[i], drugs[j])))
        if pair not in seen:
            seen.add(pair)
            neg.append(pair)
    a = ds.a + [p[0] for p in neg]
    b = ds.b + [p[1] for p in neg]
    y = np.concatenate([ds.y, np.zeros(len(neg), dtype=int)])
    return PairDataset(a, b, y, ds.smiles, ds.names)
