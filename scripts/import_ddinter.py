"""Import DDInter CSV exports into ``api/ddi/data/external_ddi.json``.

DDInter (https://ddinter2.scbdd.com) publishes downloadable CSV files grouped by
ATC code with the columns::

    DDInterID_A, Drug_A, DDInterID_B, Drug_B, Level

``Level`` is one of Major / Moderate / Minor / Unknown. Only pairs whose drug
names resolve to single ingredients in the local lexicon are kept, because the
engine can only use evidence it can attach to a known ingredient.

Usage::

    python -m scripts.import_ddinter ddinter_downloads_code_*.csv [--out PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable

os.environ.setdefault("DDI_ENABLE_RXNAV", "false")  # deterministic, offline import

from api.ddi.evidence import DEFAULT_DATA_DIR, pair_key  # noqa: E402
from api.ddi.normalize import resolve  # noqa: E402

LEVEL_RANK = {"Unknown": 0, "Minor": 1, "Moderate": 2, "Major": 3}


def _single(name: str):
    r = resolve(name)
    return r.ingredients[0] if r.recognized and len(r.ingredients) == 1 else None


def import_rows(rows: Iterable[dict]) -> dict:
    pairs: dict = {}
    stats = Counter()
    for row in rows:
        stats["rows"] += 1
        a, b = _single(row.get("Drug_A", "")), _single(row.get("Drug_B", ""))
        level = (row.get("Level") or "Unknown").strip().title()
        if level not in LEVEL_RANK:
            level = "Unknown"
        if not a or not b or a == b:
            stats["skipped_unresolved"] += 1
            continue
        key = pair_key(a, b)
        ids = [i for i in (row.get("DDInterID_A"), row.get("DDInterID_B")) if i]
        prev = pairs.get(key)
        if prev is None or LEVEL_RANK[level] > LEVEL_RANK[prev["level"]]:
            pairs[key] = {"level": level, "source_ids": sorted(set(ids) | set((prev or {}).get("source_ids", [])))}
        else:
            prev["source_ids"] = sorted(set(prev["source_ids"]) | set(ids))
        stats["kept"] += 1
    return {"pairs": pairs, "stats": dict(stats)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=DEFAULT_DATA_DIR / "external_ddi.json")
    ap.add_argument("--version", default=date.today().isoformat())
    args = ap.parse_args(argv)

    def rows():
        for path in args.csv:
            with path.open(newline="", encoding="utf-8-sig") as fh:
                yield from csv.DictReader(fh)

    result = import_rows(rows())
    payload = {"source": "DDInter 2.0", "version": args.version, "pairs": result["pairs"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(result['pairs'])} pairs to {args.out} ({result['stats']})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
