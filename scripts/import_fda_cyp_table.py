"""Import CYP / P-gp roles from the FDA tables of substrates, inhibitors and inducers.

Source (U.S. government work, public domain):
  "For Healthcare Professionals | FDA's Examples of Drugs that Interact with
   CYP Enzymes and Transporter Systems" and the companion "Drug Development and
   Drug Interactions | Table of Substrates, Inhibitors and Inducers".

The pages present HTML tables whose rows are enzymes and whose columns are
categories (sensitive / moderate sensitive substrates; strong / moderate /
weak inhibitors or inducers). This script parses every such table and writes
``api/ddi/data/fda_cyp_roles.json``, which ``api/ddi/lexicon.py`` merges at
start-up:

* roles for drugs already in the lexicon are added only where the lexicon has
  no role for that enzyme (hand-curated roles are never overwritten; any
  disagreement is listed in ``conflicts`` for review);
* drugs not yet in the lexicon are added as mechanism-only profiles, which is
  what widens the mechanism layer's coverage.

Usage::

    python -m scripts.import_fda_cyp_table [--url URL ...] [--html saved_page.html ...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from api.ddi.evidence import DEFAULT_DATA_DIR

DEFAULT_URLS = [
    "https://www.fda.gov/drugs/drug-interactions-labeling/healthcare-professionals-fdas-examples-drugs-interact-cyp-enzymes-and-transporter-systems",
    "https://www.fda.gov/drugs/drug-interactions-labeling/drug-development-and-drug-interactions-table-substrates-inhibitors-and-inducers",
]
ENZYME_RE = re.compile(r"\b(CYP\s?\d[A-Z]\d*|P-?gp|P-glycoprotein)\b", re.I)
_NAME_OK = re.compile(r"^[a-z][a-z0-9 '\-]{2,40}$")


class _Tables(HTMLParser):
    """Collect tables as (context, rows) where rows are lists of cell texts."""

    def __init__(self):
        super().__init__()
        self.tables: List[Tuple[str, List[List[str]]]] = []
        self._context = ""
        self._heading: Optional[List[str]] = None
        self._rows: Optional[List[List[str]]] = None
        self._cell: Optional[List[str]] = None
        self._sup = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "caption", "strong") and self._cell is None:
            self._heading = []
        elif tag == "table":
            self._rows = []
        elif tag == "tr" and self._rows is not None:
            self._rows.append([])
        elif tag in ("td", "th") and self._rows is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(", ")
        elif tag == "sup":
            self._sup += 1

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "caption", "strong") and self._heading is not None:
            text = " ".join("".join(self._heading).split())
            if text:
                self._context = text
            self._heading = None
        elif tag in ("td", "th") and self._cell is not None and self._rows:
            self._rows[-1].append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "table" and self._rows is not None:
            self.tables.append((self._context, [r for r in self._rows if r]))
            self._rows = None
        elif tag == "sup":
            self._sup = max(0, self._sup - 1)

    def handle_data(self, data):
        if self._sup:
            return  # footnote markers
        if self._cell is not None:
            self._cell.append(data)
        if self._heading is not None:
            self._heading.append(data)


def _enzyme(text: str) -> Optional[str]:
    m = ENZYME_RE.search(text)
    if not m:
        return None
    e = m.group(1).upper().replace(" ", "")
    if e.startswith("P"):
        return "P-gp"
    return "CYP3A4" if e == "CYP3A" else e


def _column_kind(header: str, context: str) -> Optional[Tuple[str, str]]:
    h, c = header.lower(), context.lower()
    if "substrate" in h or ("substrate" in c and "sensitive" in h):
        return ("sub", "moderate" if "moderate" in h else "sensitive") if "sensitive" in h else None
    kind = "inh" if ("inhibitor" in h or "inhibitor" in c) else "ind" if ("inducer" in h or "inducer" in c) else None
    if not kind:
        return None
    for level in ("strong", "moderate", "weak"):
        if level in h:
            return kind, level
    return None


def clean_names(cell: str) -> List[str]:
    cell = re.sub(r"\([^)]*\)", " ", cell)
    out = []
    for part in re.split(r"[,;\n]|\bor\b", cell):
        name = re.sub(r"[^a-z0-9 '\-]", " ", part.lower())
        name = " ".join(name.split()).strip(" -")
        if _NAME_OK.match(name) and not name.startswith(("none", "see ", "n a")):
            out.append(name)
    return out


def _find_header(rows: List[List[str]], context: str) -> Tuple[int, List[Optional[Tuple[str, str]]]]:
    """Pick the best header among the first rows (tables may have a title or grouped header row first)."""
    best_i, best = -1, []
    for i, row in enumerate(rows[:3]):
        kinds = [_column_kind(h, context) for h in row]
        if sum(k is not None for k in kinds) > sum(k is not None for k in best):
            best_i, best = i, kinds
    return best_i, best


def parse_html(html: str, debug: bool = False) -> Dict[str, Dict[str, Dict[str, str]]]:
    p = _Tables()
    p.feed(html)
    roles: Dict[str, Dict[str, Dict[str, str]]] = {}
    rank = {"sensitive": 2, "moderate": 1, "strong": 3, "weak": 0}
    for t_idx, (context, rows) in enumerate(p.tables):
        if debug:
            print(f"[table {t_idx}] context={context[:90]!r} rows={len(rows)}", file=sys.stderr)
            for r in rows[:3]:
                print(f"    {[c[:40] for c in r][:6]}", file=sys.stderr)
        if len(rows) < 2:
            continue
        h_idx, kinds = _find_header(rows, context)
        if h_idx < 0:
            if debug:
                print("    -> skipped: no recognised header", file=sys.stderr)
            continue
        if debug:
            print(f"    -> header row {h_idx}: {kinds}", file=sys.stderr)
        prev_enz = None
        for row in rows[h_idx + 1:]:
            if not row:
                continue
            enz = _enzyme(row[0])
            if enz:
                cells, row_kinds = row, kinds
            elif prev_enz and len(row) == len(kinds) - 1:
                # enzyme cell spans several rows (rowspan): this row has only the category cells
                enz, cells, row_kinds = prev_enz, [""] + row, kinds
            else:
                continue
            prev_enz = enz
            if len(row_kinds) != len(cells):  # tolerate ragged rows by aligning on the right
                row_kinds = (row_kinds[-len(cells):] if len(cells) < len(row_kinds)
                             else row_kinds + [None] * (len(cells) - len(row_kinds)))
            for idx, (cell, kind) in enumerate(zip(cells, row_kinds)):
                if idx == 0 or not kind:
                    continue
                field, level = kind
                for name in clean_names(cell):
                    slot = roles.setdefault(name, {"sub": {}, "inh": {}, "ind": {}})[field]
                    if enz not in slot or rank[level] > rank[slot[enz]]:
                        slot[enz] = level
    return roles


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", action="append")
    ap.add_argument("--html", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, default=DEFAULT_DATA_DIR / "fda_cyp_roles.json")
    ap.add_argument("--debug", action="store_true", help="print each table's structure to stderr")
    args = ap.parse_args(argv)

    pages = [(str(p), p.read_text(encoding="utf-8")) for p in args.html]
    if not pages:
        headers = {"User-Agent": "BioGPT-DDI research (https://github.com/TEKURU-ZENO/BioGPT-DDI)"}
        with httpx.Client(timeout=60.0, follow_redirects=True, headers=headers) as client:
            for url in args.url or DEFAULT_URLS:
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    pages.append((url, r.text))
                except httpx.HTTPError as exc:
                    print(f"  ! {url}: {exc}", file=sys.stderr)
    roles: Dict[str, Dict[str, Dict[str, str]]] = {}
    for _, html in pages:
        for name, r in parse_html(html, debug=args.debug).items():
            dst = roles.setdefault(name, {"sub": {}, "inh": {}, "ind": {}})
            for field in ("sub", "inh", "ind"):
                for enz, level in r[field].items():
                    dst[field].setdefault(enz, level)
    if not roles:
        print("no roles parsed - page layout may have changed", file=sys.stderr)
        return 1
    payload = {"source": [u for u, _ in pages], "retrieved": date.today().isoformat(), "roles": roles}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    print(f"parsed roles for {len(roles)} drugs -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
