"""Build an expert-panel reference from the ONC high/low-priority DDI lists.

* High-priority list: Phansalkar S et al. High-priority drug-drug interactions
  for use in electronic health records. JAMIA 2012;19(5):735-43
  (doi:10.1136/amiajnl-2011-000612). 15 interactions an expert panel of
  pharmacists, physicians and knowledge-base vendors judged should always alert.
* Low-priority list: Phansalkar S et al. Drug-drug interactions that should be
  non-interruptive in order to reduce alert fatigue in electronic health
  records. JAMIA 2013;20(3):489-93.

The pairs must be transcribed from the papers' tables into
``eval/references/onc_transcription.csv`` (columns ``list, object_a,
object_b, citation``) by someone with access to the papers. Objects are
ingredient names or ``@tag`` classes from api/ddi/lexicon.py (e.g. ``@ppi``,
``@maoi``). They are deliberately not typed from memory here.

High-priority pairs are written with severity "Major" (the engine is expected
to grade them Major or Contraindicated); low-priority pairs are written as
"Minor" (an engine grading them Major contributes to alert fatigue).

Usage::

    python -m scripts.references.onc --out eval/references/onc.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List

from api.ddi.lexicon import DRUGS

from .common import write_reference

TRANSCRIPTION = Path("eval/references/onc_transcription.csv")


def expand(obj: str) -> List[str]:
    obj = obj.strip().lower()
    if obj.startswith("@"):
        return sorted(n for n, d in DRUGS.items() if d.has(obj[1:]))
    return [obj] if obj in DRUGS else []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcription", type=Path, default=TRANSCRIPTION)
    ap.add_argument("--out", type=Path, default=Path("eval/references/onc.csv"))
    args = ap.parse_args(argv)

    with args.transcription.open(newline="", encoding="utf-8") as fh:
        entries = [r for r in csv.DictReader(fh) if (r.get("object_a") or "").strip()]
    if not entries:
        print(f"{args.transcription} has no transcribed pairs yet - see the module docstring", file=sys.stderr)
        return 1
    rows, unmapped = [], []
    for e in entries:
        a_list, b_list = expand(e["object_a"]), expand(e["object_b"])
        if not a_list or not b_list:
            unmapped.append(f"{e['object_a']} + {e['object_b']}")
            continue
        sev = "Major" if e["list"].strip().lower().startswith("high") else "Minor"
        for a in a_list:
            for b in b_list:
                rows.append({"drug1": a, "drug2": b, "severity": sev, "source": f"ONC {e['list']}-priority list",
                             "source_id": e.get("citation", ""), "note": f"{e['object_a']} + {e['object_b']}"})
    n = write_reference(rows, args.out)
    print(f"{len(entries)} transcribed entries -> {n} ingredient pairs; not in lexicon: {unmapped or 'none'}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
