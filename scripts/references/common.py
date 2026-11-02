"""Shared helpers for reference builders."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, Iterable, Optional

os.environ.setdefault("DDI_ENABLE_RXNAV", "false")  # deterministic, offline name resolution

from api.ddi.normalize import resolve  # noqa: E402

FIELDS = ["drug1", "drug2", "severity", "source", "source_id", "note"]


def single_ingredient(name: str) -> Optional[str]:
    r = resolve(name or "")
    return r.ingredients[0] if r.recognized and len(r.ingredients) == 1 else None


RANK = {"Contraindicated": 6, "Major": 5, "Moderate": 4, "Precaution": 3, "Minor": 2, "Unknown": 1, "None": 0}


def write_reference(rows: Iterable[Dict[str, str]], out: Path) -> int:
    """Write one row per unordered pair, keeping the highest grade if a source lists it twice."""
    best: Dict[tuple, Dict[str, str]] = {}
    for r in rows:
        if r["drug1"] == r["drug2"]:
            continue
        key = tuple(sorted((r["drug1"], r["drug2"])))
        if key not in best or RANK.get(r["severity"], 0) > RANK.get(best[key]["severity"], 0):
            best[key] = r
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for key in sorted(best):
            w.writerow({k: best[key].get(k, "") for k in FIELDS})
    return len(best)
