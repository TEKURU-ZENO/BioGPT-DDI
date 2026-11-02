"""Build a contraindication reference from KEGG DDI (KEGG MEDICUS).

KEGG extracts interactions from package inserts (Japanese and US labels) and
labels each pair CI (contraindicated) and/or P (precaution). Licence: academic
use only; bulk download is not permitted, so this queries the REST API per
drug and keeps only pairs between this project's ingredients.

API (https://www.kegg.jp/kegg/rest/keggapi.html)::

    GET https://rest.kegg.jp/find/drug/<name>   -> "dr:D00564<TAB>Warfarin (JP18/USP); ..."
    GET https://rest.kegg.jp/ddi/<D number>     -> "dr:D00564<TAB>dr:D00XXX<TAB>CI,P<TAB><mechanism>"

Severity in the output: "Contraindicated" for CI, "Precaution" for P only.

Usage::

    python -m scripts.references.kegg --out eval/references/kegg.csv [--only warfarin,fluconazole]
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from api.ddi.lexicon import DRUGS

from .common import write_reference

BASE = "https://rest.kegg.jp"


def parse_find(text: str, ingredient: str) -> Optional[str]:
    """Pick the KEGG D number whose first listed name matches the ingredient."""
    want = ingredient.lower()
    for line in text.splitlines():
        if "\t" not in line:
            continue
        entry, names = line.split("\t", 1)
        first = re.sub(r"\s*\(.*?\)", "", names.split(";")[0]).strip().lower()
        first = re.sub(r"\s+(hydrochloride|sodium|potassium|calcium|maleate|mesylate|besylate|succinate|"
                       r"tartrate|citrate|sulfate|phosphate|hyclate|hydrate|monohydrate)$", "", first)
        if first == want:
            return entry.replace("dr:", "")
    return None


def parse_ddi(text: str) -> List[tuple]:
    out = []
    for line in text.splitlines():
        cols = line.split("\t")
        if len(cols) < 3 or not cols[0].startswith("dr:") or not cols[1].startswith("dr:"):
            continue
        labels = {x.strip() for x in cols[2].split(",")}
        out.append((cols[0][3:], cols[1][3:], labels, cols[3] if len(cols) > 3 else ""))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("eval/references/kegg.csv"))
    ap.add_argument("--only")
    ap.add_argument("--sleep", type=float, default=0.4, help="KEGG asks for modest request rates")
    args = ap.parse_args(argv)

    names = [n.strip() for n in args.only.split(",")] if args.only else sorted(DRUGS)
    d_of: Dict[str, str] = {}
    rows = []
    with httpx.Client(timeout=30.0) as client:
        for name in names:
            try:
                r = client.get(f"{BASE}/find/drug/{name}")
                d = parse_find(r.text, name) if r.status_code == 200 else None
            except httpx.HTTPError as exc:
                print(f"  ! find {name}: {exc}", file=sys.stderr)
                d = None
            if d:
                d_of[d] = name
            time.sleep(args.sleep)
        print(f"mapped {len(d_of)}/{len(names)} ingredients to KEGG D numbers", file=sys.stderr)
        for d in sorted(d_of):
            try:
                r = client.get(f"{BASE}/ddi/{d}")
            except httpx.HTTPError as exc:
                print(f"  ! ddi {d}: {exc}", file=sys.stderr)
                continue
            if r.status_code != 200:
                continue
            for a, b, labels, mech in parse_ddi(r.text):
                if a in d_of and b in d_of:
                    sev = "Contraindicated" if "CI" in labels else "Precaution" if "P" in labels else None
                    if sev:
                        rows.append({"drug1": d_of[a], "drug2": d_of[b], "severity": sev, "source": "KEGG DDI",
                                     "source_id": f"{a}|{b}", "note": mech[:200]})
            time.sleep(args.sleep)
    n = write_reference(rows, args.out)
    print(f"wrote {n} pairs to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
