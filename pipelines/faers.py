"""FAERS disproportionality screening for drug-drug interaction signals (Phase 4).

For a drug pair (A, B) and an adverse-event term R (MedDRA preferred term),
openFDA report counts give 2x2 tables for A alone, B alone and A+B together.
The reporting odds ratio (ROR) is computed for each:

                    R      not R
    exposure        a      b
    no exposure     c      d          ROR = (a/b) / (c/d),  95% CI via log-normal

An interaction signal is raised when the combination's ROR lower 95% bound
exceeds 1 *and* the combination's ROR exceeds both single-drug RORs (the
"combination exceeds components" heuristic; cf. Norén et al., Stat Med 2008
for shrinkage-based alternatives).

Caveats: spontaneous reports are subject to notoriety, stimulated reporting,
confounding by indication and duplicates. A signal is a hypothesis for
pharmacist review, never evidence of causation.

Usage::

    python -m pipelines.faers warfarin fluconazole --reaction HAEMORRHAGE
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Optional

import httpx

OPENFDA_EVENTS = "https://api.fda.gov/drug/event.json"


@dataclass
class Table:
    a: int  # exposed, with event
    b: int  # exposed, without event
    c: int  # unexposed, with event
    d: int  # unexposed, without event


def ror(t: Table) -> Optional[dict]:
    """Reporting odds ratio with 95% CI; Haldane correction when a cell is zero."""
    a, b, c, d = t.a, t.b, t.c, t.d
    if min(a, b, c, d) < 0:
        raise ValueError("negative count")
    if a == 0:
        return None
    if 0 in (b, c, d):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    value = (a / b) / (c / d)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return {"ror": value, "lower95": math.exp(math.log(value) - 1.96 * se),
            "upper95": math.exp(math.log(value) + 1.96 * se), "n_cases": t.a}


def table_from_counts(n_total: int, n_event: int, n_exposed: int, n_exposed_event: int) -> Table:
    a = n_exposed_event
    b = n_exposed - n_exposed_event
    c = n_event - n_exposed_event
    d = n_total - n_exposed - c
    return Table(a, b, c, d)


def interaction_signal(combo: Optional[dict], single_a: Optional[dict], single_b: Optional[dict],
                       min_cases: int = 3) -> bool:
    if not combo or combo["n_cases"] < min_cases or combo["lower95"] <= 1:
        return False
    singles = [s["ror"] for s in (single_a, single_b) if s]
    return all(combo["ror"] > s for s in singles)


def _q(drug: str) -> str:
    return f'patient.drug.openfda.generic_name.exact:"{drug.upper()}"'


def _count(client: httpx.Client, search: Optional[str], api_key: Optional[str]) -> int:
    params = {"limit": 1}
    if search:
        params["search"] = search
    if api_key:
        params["api_key"] = api_key
    r = client.get(OPENFDA_EVENTS, params=params)
    if r.status_code == 404:  # openFDA: no matching records
        return 0
    r.raise_for_status()
    return int(r.json()["meta"]["results"]["total"])


def screen(drug_a: str, drug_b: str, reaction: str, api_key: Optional[str] = None) -> dict:
    ev = f'patient.reaction.reactionmeddrapt.exact:"{reaction.upper()}"'
    with httpx.Client(timeout=30.0) as client:
        n_total = _count(client, None, api_key)
        n_event = _count(client, ev, api_key)
        counts = {}
        for label, q in (("a", _q(drug_a)), ("b", _q(drug_b)), ("ab", f"{_q(drug_a)} AND {_q(drug_b)}")):
            counts[label] = (_count(client, q, api_key), _count(client, f"{q} AND {ev}", api_key))
    res = {k: ror(table_from_counts(n_total, n_event, *v)) for k, v in counts.items()}
    return {
        "drugs": [drug_a, drug_b], "reaction": reaction, "n_reports": n_total,
        "ror": {"combination": res["ab"], drug_a: res["a"], drug_b: res["b"]},
        "signal": interaction_signal(res["ab"], res["a"], res["b"]),
        "caveat": "Disproportionality in spontaneous reports is hypothesis-generating only.",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("drug_a")
    ap.add_argument("drug_b")
    ap.add_argument("--reaction", required=True, help="MedDRA preferred term, e.g. HAEMORRHAGE")
    args = ap.parse_args(argv)
    print(json.dumps(screen(args.drug_a, args.drug_b, args.reaction, os.getenv("OPENFDA_API_KEY")), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
