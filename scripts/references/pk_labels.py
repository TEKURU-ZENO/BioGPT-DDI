"""Extract observed AUC changes for drug pairs from FDA labels (openFDA).

FDA labels report clinical DDI study results in sections 7 and 12.3, e.g.
"Coadministration with ketoconazole increased the AUC of midazolam 15-fold" or
"rifampin decreased tadalafil AUC by 88%". This builder pulls those sections
from openFDA for every lexicon drug and extracts sentences that name another
lexicon drug, mention AUC, and state a fold or percent change.

Extraction is heuristic: direction (which drug is the victim) is inferred from
"AUC of <drug>" / "<drug> AUC" phrasing, otherwise the label's own drug is
assumed to be the victim and the row is marked ``direction=assumed``. Every
row keeps its source sentence, and the PK evaluation lists the largest
disagreements so they can be audited by eye.

Output columns: victim, perpetrator, observed_aucr, source, source_id, direction, sentence

Usage::

    python -m scripts.references.pk_labels --out eval/references/pk_labels.csv [--only midazolam,simvastatin]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional

import httpx

from api.ddi.lexicon import DRUGS, SYNONYMS

OPENFDA = "https://api.fda.gov/drug/label.json"
FIELDS = ["victim", "perpetrator", "observed_aucr", "source", "source_id", "direction", "sentence"]
TEXT_FIELDS = ("drug_interactions", "clinical_pharmacology", "pharmacokinetics")

_NAMES = {n: n for n in DRUGS}
_NAMES.update({k: v for k, v in SYNONYMS.items() if isinstance(v, str) and len(k) > 4})
_NAME_RE = re.compile(r"(?<![\w-])(" + "|".join(sorted(map(re.escape, _NAMES), key=len, reverse=True)) + r")(?![\w-])",
                      re.I)
_FOLD = re.compile(r"(\d+(?:\.\d+)?)\s*-?\s*(?:fold|times)", re.I)
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%", re.I)
_DECREASE = re.compile(r"\b(decreas\w*|reduc\w*|lower\w*)\b", re.I)
_INCREASE = re.compile(r"\b(increas\w*|rais\w*|elevat\w*|higher)\b", re.I)


def sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text) if s.strip()]


def _magnitude(sent: str, auc_pos: int):
    """The fold/percent value closest to the AUC mention (after it within 140 chars, or before within 60).

    Values attached to other parameters ("Cmax by 46%") are skipped when an AUC value is available, because the
    closest match to the AUC token wins.
    """
    best = None
    for kind, rx in (("fold", _FOLD), ("pct", _PCT)):
        for m in rx.finditer(sent):
            if kind == "pct" and re.match(r"%?\s*(ci\b|confidence|prediction interval)", sent[m.end():m.end() + 25].lstrip("%").strip(), re.I):
                continue  # "(90% CI: ...)" is a confidence level, not an exposure change
            d = m.start() - auc_pos
            if -60 <= d <= 140:
                dist = abs(d)
                if best is None or dist < best[0]:
                    best = (dist, float(m.group(1)), kind, m.start())
    return best[1:] if best else None


def _direction(sent: str, pos: int):
    """True for a decrease, False for an increase, None if no direction word is near the magnitude."""
    window_start = max(0, pos - 80)
    cands = []
    for rx, is_dec in ((_DECREASE, True), (_INCREASE, False)):
        for m in rx.finditer(sent, window_start, min(len(sent), pos + 40)):
            if re.search(r"\b(not|no)\s+\w*\s*$", sent[max(0, m.start() - 12):m.start()]):
                continue  # "did not decrease"
            cands.append((abs(m.start() - pos), is_dec))
    return min(cands)[1] if cands else None


def extract(text: str, label_drug: str) -> List[dict]:
    out = []
    for sent in sentences(text):
        auc = re.search(r"\bAUC", sent)
        if not auc:
            continue
        mentioned = []
        for m in _NAME_RE.finditer(sent):
            ing = _NAMES[m.group(1).lower()]
            if ing not in mentioned:
                mentioned.append(ing)
        others = [d for d in mentioned if d != label_drug]
        if len(others) != 1:  # ambiguous or no co-administered drug named
            continue
        other = others[0]
        mag = _magnitude(sent, auc.start())
        if not mag:
            continue
        value, kind, pos = mag
        decrease = _direction(sent, pos)
        if decrease is None:
            continue
        if kind == "fold":
            aucr = 1 / value if decrease else value
        else:
            p = value / 100
            aucr = 1 - p if decrease else 1 + p
        if aucr <= 0:
            continue
        of = re.search(r"AUC\w*(?:\s*\([^)]*\))?\s+(?:values?\s+)?of\s+(?:the\s+)?([A-Za-z][\w\- ]{2,40})", sent)
        pre = re.search(r"([A-Za-z][\w\-]{2,30})\s+AUC", sent)
        victim, direction = label_drug, "assumed"
        for grp in (of.group(1) if of else None, pre.group(1) if pre else None):
            if not grp:
                continue
            hit = _NAME_RE.search(grp)
            if hit:
                victim, direction = _NAMES[hit.group(1).lower()], "explicit"
                break
        perp = other if victim == label_drug else label_drug
        if victim not in (label_drug, other):
            continue
        out.append({"victim": victim, "perpetrator": perp, "observed_aucr": round(aucr, 3),
                    "direction": direction, "sentence": sent[:400]})
    return out


def fetch_label(client: httpx.Client, name: str) -> Optional[dict]:
    for search in (f'openfda.generic_name.exact:"{name.upper()}"', f'openfda.generic_name:"{name}"'):
        r = client.get(OPENFDA, params={"search": search, "limit": 1})
        if r.status_code == 200 and r.json().get("results"):
            return r.json()["results"][0]
    return None


def label_rows(name: str, label: dict) -> Iterable[dict]:
    text = " ".join(" ".join(label.get(f) or []) for f in TEXT_FIELDS)
    for row in extract(text, name):
        yield {**row, "source": "FDA label (openFDA)", "source_id": label.get("set_id", "")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("eval/references/pk_labels.csv"))
    ap.add_argument("--only")
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args(argv)
    names = [n.strip() for n in args.only.split(",")] if args.only else sorted(DRUGS)
    rows = []
    with httpx.Client(timeout=30.0) as client:
        for name in names:
            try:
                lab = fetch_label(client, name)
            except httpx.HTTPError as exc:
                print(f"  ! {name}: {exc}", file=sys.stderr)
                lab = None
            if lab:
                rows.extend(label_rows(name, lab))
            time.sleep(args.sleep)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"extracted {len(rows)} AUC observations from {len(names)} labels -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
