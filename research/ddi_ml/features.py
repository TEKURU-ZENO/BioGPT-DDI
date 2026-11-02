"""Order-invariant pair features from molecular fingerprints."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Dict, Sequence

import numpy as np

try:  # pragma: no cover - exercised when rdkit is installed
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdFingerprintGenerator

    RDLogger.DisableLog("rdApp.*")
    _GEN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)
    HAVE_RDKIT = True
except Exception:  # pragma: no cover
    HAVE_RDKIT = False

N_BITS = 1024


@lru_cache(maxsize=100_000)
def fingerprint(smiles: str, method: str = "auto") -> np.ndarray:
    """1024-bit Morgan (radius 2) fingerprint; SMILES n-gram hashing as a fallback."""
    if method in ("auto", "morgan") and HAVE_RDKIT:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            return _GEN.GetFingerprintAsNumPy(mol).astype(np.float32)
        if method == "morgan":
            return np.zeros(N_BITS, dtype=np.float32)
    v = np.zeros(N_BITS, dtype=np.float32)
    for n in (2, 3, 4):
        for k in range(len(smiles) - n + 1):
            h = int(hashlib.blake2b(smiles[k:k + n].encode(), digest_size=4).hexdigest(), 16)
            v[h % N_BITS] = 1.0
    return v


def pair_features(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Symmetric combination so f(a, b) == f(b, a)."""
    return np.concatenate([a + b, a * b])


def featurize(a_ids: Sequence[str], b_ids: Sequence[str], smiles: Dict[str, str], method: str = "auto") -> np.ndarray:
    return np.stack([pair_features(fingerprint(smiles[x], method), fingerprint(smiles[y], method))
                     for x, y in zip(a_ids, b_ids)])
