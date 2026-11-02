"""Normalise a published table of observed AUC ratios into the PK reference format.

Use for the CR/IR compilations (Ohno 2007; Hisaka 2009; the extended AAPS J
2015 analysis) or exports from PK-DB (https://pk-db.com). Column names are
matched case-insensitively:

* victim:       substrate | victim | object | victim_drug
* perpetrator:  perpetrator | inhibitor | inducer | precipitant
* AUC ratio:    aucr | auc_ratio | auc ratio | observed_aucr | ratio
* source:       source | reference | pmid | doi  (optional)

Usage::

    python -m scripts.references.pk_table supplement.csv --source "AAPS J 2015 suppl." --out eval/references/pk_crir.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .common import single_ingredient

COLS = {
    "victim": ("substrate", "victim", "object", "victim_drug"),
    "perpetrator": ("perpetrator", "inhibitor", "inducer", "precipitant"),
    "aucr": ("aucr", "auc_ratio", "auc ratio", "observed_aucr", "ratio"),
    "source": ("source", "reference", "pmid", "doi"),
}
FIELDS = ["victim", "perpetrator", "observed_aucr", "source", "source_id", "direction", "sentence"]


def _col(header, keys):
    low = {h.lower().strip(): h for h in header}
    return next((low[k] for k in keys if k in low), None)


def convert(rows, header, source_label: str):
    c = {k: _col(header, v) for k, v in COLS.items()}
    if not (c["victim"] and c["perpetrator"] and c["aucr"]):
        raise ValueError(f"could not find victim/perpetrator/AUC-ratio columns in {header}")
    out, skipped = [], 0
    for r in rows:
        v, p = single_ingredient(r[c["victim"]]), single_ingredient(r[c["perpetrator"]])
        try:
            aucr = float(str(r[c["aucr"]]).replace(",", "."))
        except ValueError:
            aucr = None
        if not v or not p or not aucr or aucr <= 0:
            skipped += 1
            continue
        out.append({"victim": v, "perpetrator": p, "observed_aucr": aucr, "source": source_label,
                    "source_id": r.get(c["source"], "") if c["source"] else "", "direction": "explicit",
                    "sentence": ""})
    return out, skipped


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("table", type=Path)
    ap.add_argument("--source", required=True, help="citation for the table")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    with args.table.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows, skipped = convert(list(reader), reader.fieldnames or [], args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows ({skipped} skipped: unknown drug or bad ratio) to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
