"""Evaluate the engine against a gold standard and (optionally) a reference grading.

1. Gold standard (``eval/gold_standard.csv``): columns
   ``drug1, drug2, expected (interaction|none_known|unrecognized), min_severity``.
   Reports safety-critical recall (Major/Contraindicated detected at >= the
   expected grade), under-call rate, false-alert rate on non-interacting pairs
   and correct handling of unrecognised input.

2. Reference grading (``--reference``): a CSV ``drug1, drug2, severity`` from
   a pharmacist panel or another database. Reports exact agreement,
   quadratic-weighted Cohen's kappa on the ordinal scale
   None < Minor < Moderate < Major < Contraindicated, and the confusion matrix.

Usage::

    python -m scripts.evaluate [--gold eval/gold_standard.csv] [--reference panel.csv] [--out eval/report.md]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

os.environ.setdefault("DDI_ENABLE_RXNAV", "false")

from api.ddi.engine import SEVERITY_RANK, analyze_pair  # noqa: E402

SCALE = ["None", "Minor", "Moderate", "Major", "Contraindicated"]


def _ordinal(sev: str) -> Optional[int]:
    if sev in ("None known", "None", "none", ""):
        return 0
    return SEVERITY_RANK.get(sev.title() if sev.lower() != "contraindicated" else "Contraindicated")


def evaluate_gold(rows: List[dict]) -> dict:
    res = Counter()
    misses = []
    for r in rows:
        out = analyze_pair(r["drug1"], r["drug2"])
        exp = r["expected"]
        res[f"n_{exp}"] += 1
        if exp == "interaction":
            ok = out["status"] == "interaction_found" and SEVERITY_RANK[out["severity"]] >= SEVERITY_RANK[r["min_severity"]]
            critical = SEVERITY_RANK[r["min_severity"]] >= SEVERITY_RANK["Major"]
            res["critical_total"] += critical
            res["critical_hit"] += critical and ok
            res["interaction_hit"] += ok
            if out["status"] == "interaction_found" and not ok:
                res["under_called"] += 1
            if not ok:
                misses.append((r["drug1"], r["drug2"], r["min_severity"], out["severity"]))
        elif exp == "none_known":
            fp = out["status"] == "interaction_found"
            res["false_alerts"] += fp
            if fp:
                misses.append((r["drug1"], r["drug2"], "None known", out["severity"]))
        elif exp == "unrecognized":
            ok = out["status"] == "unrecognized_drug" and out["severity"] == "Unknown"
            res["unrecognized_ok"] += ok
            if not ok:
                misses.append((r["drug1"], r["drug2"], "Unknown", out["severity"]))
    div = lambda a, b: (a / b) if b else float("nan")
    return {
        "pairs": len(rows),
        "critical_recall": div(res["critical_hit"], res["critical_total"]),
        "interaction_recall": div(res["interaction_hit"], res["n_interaction"]),
        "under_call_rate": div(res["under_called"], res["n_interaction"]),
        "false_alert_rate": div(res["false_alerts"], res["n_none_known"]),
        "unrecognized_handled": div(res["unrecognized_ok"], res["n_unrecognized"]),
        "misses": misses,
    }


def weighted_kappa(a: List[int], b: List[int], k: int = len(SCALE)) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x][y] += 1
    ra = [sum(row) for row in obs]
    rb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = lambda i, j: ((i - j) ** 2) / ((k - 1) ** 2)
    num = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    den = sum(w(i, j) * ra[i] * rb[j] / n for i in range(k) for j in range(k))
    return 1 - num / den if den else 1.0


def evaluate_reference(rows: List[dict]) -> dict:
    eng, ref, skipped = [], [], 0
    for r in rows:
        out = analyze_pair(r["drug1"], r["drug2"])
        e, f = _ordinal(out["severity"]), _ordinal(r["severity"])
        if e is None or f is None:
            skipped += 1
            continue
        eng.append(e)
        ref.append(f)
    confusion = Counter(zip(ref, eng))
    return {
        "pairs": len(eng), "skipped_unknown": skipped,
        "exact_agreement": sum(x == y for x, y in zip(eng, ref)) / len(eng) if eng else float("nan"),
        "weighted_kappa": weighted_kappa(ref, eng),
        "engine_lower_than_reference": sum(x < y for x, y in zip(eng, ref)),
        "engine_higher_than_reference": sum(x > y for x, y in zip(eng, ref)),
        "confusion": {f"{SCALE[i]}->{SCALE[j]}": c for (i, j), c in sorted(confusion.items())},
    }


def report(gold: dict, ref: Optional[dict]) -> str:
    pct = lambda x: "n/a" if x != x else f"{100 * x:.1f}%"
    lines = ["# BioGPT-DDI evaluation report", "", "## Gold standard", "",
             f"| Metric | Value |", "|---|---|",
             f"| Pairs | {gold['pairs']} |",
             f"| Safety-critical recall (Major/Contraindicated at >= expected grade) | {pct(gold['critical_recall'])} |",
             f"| Interaction recall (at >= expected grade) | {pct(gold['interaction_recall'])} |",
             f"| Under-call rate | {pct(gold['under_call_rate'])} |",
             f"| False-alert rate (non-interacting pairs) | {pct(gold['false_alert_rate'])} |",
             f"| Unrecognised input handled safely | {pct(gold['unrecognized_handled'])} |", ""]
    if gold["misses"]:
        lines += ["### Misses", "", "| Drug 1 | Drug 2 | Expected | Engine |", "|---|---|---|---|"]
        lines += [f"| {a} | {b} | {e} | {g} |" for a, b, e, g in gold["misses"]]
        lines.append("")
    if ref:
        lines += ["## Agreement with reference grading", "", "| Metric | Value |", "|---|---|",
                  f"| Pairs compared | {ref['pairs']} (skipped {ref['skipped_unknown']}) |",
                  f"| Exact agreement | {pct(ref['exact_agreement'])} |",
                  f"| Quadratic-weighted kappa | {ref['weighted_kappa']:.3f} |",
                  f"| Engine lower than reference | {ref['engine_lower_than_reference']} |",
                  f"| Engine higher than reference | {ref['engine_higher_than_reference']} |", "",
                  "Confusion (reference -> engine): " + ", ".join(f"{k}: {v}" for k, v in ref["confusion"].items()), ""]
    lines.append("_The gold standard was assembled by the developers from product labeling and regulatory "
                 "communications; it is a regression set, not an independent clinical validation._")
    return "\n".join(lines) + "\n"


def _read(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", type=Path, default=Path("eval/gold_standard.csv"))
    ap.add_argument("--reference", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--min-critical-recall", type=float, default=1.0,
                    help="exit non-zero if safety-critical recall falls below this")
    args = ap.parse_args(argv)
    gold = evaluate_gold(_read(args.gold))
    ref = evaluate_reference(_read(args.reference)) if args.reference else None
    text = report(gold, ref)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if gold["critical_recall"] >= args.min_critical_recall else 1


if __name__ == "__main__":
    raise SystemExit(main())
