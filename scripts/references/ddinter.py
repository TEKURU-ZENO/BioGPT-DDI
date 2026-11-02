"""Build a severity reference from DDInter (Xiong et al., NAR 2021; DDInter 2.0, NAR 2025).

DDInter severities (Major / Moderate / Minor / Unknown) were curated by a
clinical pharmacist team, independently of this project. DDInter publishes
per-ATC-code CSV exports with columns::

    DDInterID_A, Drug_A, DDInterID_B, Drug_B, Level

DDInter lists interacting pairs only. ``--negatives N`` samples N pairs of
drugs that DDInter covers but does not list together, labelled "None". This
assumes DDInter is complete for those drugs, which it is not, so specificity
estimated from them is approximate and is reported as such.

Usage::

    python -m scripts.references.ddinter --download --out eval/references/ddinter.csv
    python -m scripts.references.ddinter ddinter_downloads_code_*.csv --negatives 500
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from pathlib import Path
from typing import Iterable, List

import httpx

from .common import single_ingredient, write_reference

# DDInter export files, one per ATC first-level code. Override with --url if the site layout changes.
ATC_CODES = ["A", "B", "D", "H", "L", "P", "R", "V"]
DEFAULT_URLS = [f"https://ddinter.scbdd.com/static/media/download/ddinter_downloads_code_{c}.csv" for c in ATC_CODES]
LEVELS = {"major": "Major", "moderate": "Moderate", "minor": "Minor", "unknown": "Unknown"}


def parse(rows: Iterable[dict], stats: dict) -> List[dict]:
    out = []
    for row in rows:
        stats["rows"] = stats.get("rows", 0) + 1
        a, b = single_ingredient(row.get("Drug_A", "")), single_ingredient(row.get("Drug_B", ""))
        for raw, ing in ((row.get("Drug_A", ""), a), (row.get("Drug_B", ""), b)):
            stats.setdefault("drugs_seen", set()).add(raw.lower())
            if ing:
                stats.setdefault("drugs_known", set()).add(raw.lower())
        if not a or not b or a == b:
            continue
        out.append({"drug1": a, "drug2": b, "severity": LEVELS.get((row.get("Level") or "").strip().lower(), "Unknown"),
                    "source": "DDInter", "source_id": f"{row.get('DDInterID_A', '')}|{row.get('DDInterID_B', '')}"})
    return out


def sample_negatives(pos: List[dict], n: int, seed: int = 0) -> List[dict]:
    drugs = sorted({r["drug1"] for r in pos} | {r["drug2"] for r in pos})
    listed = {tuple(sorted((r["drug1"], r["drug2"]))) for r in pos}
    rng, out, tries = random.Random(seed), [], 0
    while len(out) < n and tries < n * 100 and len(drugs) > 1:
        tries += 1
        a, b = sorted(rng.sample(drugs, 2))
        if (a, b) not in listed:
            listed.add((a, b))
            out.append({"drug1": a, "drug2": b, "severity": "None", "source": "DDInter (sampled negative)",
                        "note": "not listed together in DDInter; assumes completeness"})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="*", type=Path)
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--url", action="append", help="override download URL(s)")
    ap.add_argument("--negatives", type=int, default=0)
    ap.add_argument("--out", type=Path, default=Path("eval/references/ddinter.csv"))
    args = ap.parse_args(argv)

    texts = []
    if args.download:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            for url in args.url or DEFAULT_URLS:
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    texts.append(r.text)
                except httpx.HTTPError as exc:
                    print(f"  ! {url}: {exc}", file=sys.stderr)
    texts += [p.read_text(encoding="utf-8-sig") for p in args.csv]
    if not texts:
        print("no DDInter data (pass CSV files or --download)", file=sys.stderr)
        return 1

    stats: dict = {}
    pos = []
    for t in texts:
        pos += parse(csv.DictReader(io.StringIO(t.lstrip("﻿"))), stats)
    neg = sample_negatives(pos, args.negatives) if args.negatives else []
    n = write_reference(pos + neg, args.out)
    seen, known = len(stats.get("drugs_seen", ())), len(stats.get("drugs_known", ()))
    print(f"{stats.get('rows', 0)} DDInter rows; {known}/{seen} drugs in lexicon "
          f"({100 * known / max(seen, 1):.1f}%); wrote {n} pairs ({len(neg)} sampled negatives) to {args.out}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
