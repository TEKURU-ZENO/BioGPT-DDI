"""Validate the static-model exposure estimates against observed AUC ratios.

Reference rows (``victim, perpetrator, observed_aucr, source, ...``) come from
``scripts/references/pk_labels.py`` (FDA labels) and
``scripts/references/pk_table.py`` (published compilations such as the CR/IR
tables, or PK-DB exports). For each row the engine's estimate for that victim
and perpetrator is compared with the observation.

Metrics (standard for DDI prediction; e.g. Guest et al., Drug Metab Dispos
2011, for the 2-fold criterion and its limits near AUCR ~ 1):
* fold error FE = predicted / observed; GMFE = 10^mean(|log10 FE|)
* share of predictions within 1.25-, 1.5- and 2-fold of observed
* share of observations inside the engine's stated plausible range
* FDA magnitude category agreement (strong / moderate / weak / none),
  derived from predicted and observed AUCR
* coverage: share of observed interactions (|AUCR - 1| >= 0.25) for which the
  engine produced any estimate at all

``--holdout-seed`` splits the reference into calibration and holdout halves
(by drug pair) so that any future drug-specific parameter tuning can be done on
the calibration half and reported on the untouched holdout.

Usage::

    python -m scripts.evaluate_pk eval/references/pk_labels.csv [more.csv] --out eval/pk_report.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

os.environ.setdefault("DDI_ENABLE_RXNAV", "false")

from api.ddi.engine import analyze_pair  # noqa: E402

from scripts.evaluate import isolated_engine  # noqa: E402


def category(aucr: float) -> str:
    """FDA magnitude categories for a perpetrator's effect on a sensitive substrate."""
    if aucr >= 5:
        return "strong-inhibition"
    if aucr >= 2:
        return "moderate-inhibition"
    if aucr >= 1.25:
        return "weak-inhibition"
    if aucr <= 0.2:
        return "strong-induction"
    if aucr <= 0.5:
        return "moderate-induction"
    if aucr <= 0.8:
        return "weak-induction"
    return "none"


def engine_estimate(victim: str, perp: str) -> Optional[dict]:
    res = analyze_pair(victim, perp)
    for f in res.get("findings", []):
        est = f.get("pk_estimate")
        if est and est.get("victim") == victim and est.get("perpetrator") == perp:
            return est
    return None


def _split(victim: str, perp: str, seed: int) -> str:
    h = hashlib.sha256(f"{seed}:{victim}|{perp}".encode()).digest()[0]
    return "calibration" if h % 2 == 0 else "holdout"


def evaluate(rows: List[dict], holdout_seed: Optional[int] = None) -> Dict[str, dict]:
    # Collapse duplicate observations of the same pair to their geometric mean.
    grouped: Dict[tuple, List[float]] = {}
    sources: Dict[tuple, set] = {}
    for r in rows:
        try:
            v = float(r["observed_aucr"])
        except (TypeError, ValueError):
            continue
        if v <= 0:
            continue
        key = (r["victim"], r["perpetrator"])
        grouped.setdefault(key, []).append(v)
        sources.setdefault(key, set()).add(r.get("source", ""))
    obs = {k: math.exp(sum(map(math.log, vs)) / len(vs)) for k, vs in grouped.items()}

    subsets: Dict[str, List[tuple]] = {"all": list(obs)}
    if holdout_seed is not None:
        for k in obs:
            subsets.setdefault(_split(*k, holdout_seed), []).append(k)

    results = {}
    for name, keys in subsets.items():
        recs = []
        for victim, perp in keys:
            o = obs[(victim, perp)]
            est = engine_estimate(victim, perp)
            recs.append({"victim": victim, "perpetrator": perp, "observed": o, "est": est,
                         "sources": sorted(sources[(victim, perp)])})
        meaningful = [r for r in recs if abs(math.log(r["observed"])) >= math.log(1.25)]
        scored = [r for r in recs if r["est"]]
        fe = [r["est"]["auc_ratio"] / r["observed"] for r in scored]
        absl = [abs(math.log10(x)) for x in fe]
        def within(f: float, fe: List[float] = fe) -> float:
            return sum(1 / f <= x <= f for x in fe) / len(fe) if fe else float("nan")

        in_range = [r["est"]["auc_ratio_range"][0] <= r["observed"] <= r["est"]["auc_ratio_range"][1] for r in scored]
        cat = [category(r["est"]["auc_ratio"]) == category(r["observed"]) for r in scored]
        scored.sort(key=lambda r: -abs(math.log(r["est"]["auc_ratio"] / r["observed"])))
        results[name] = {
            "pairs": len(recs),
            "coverage": (sum(1 for r in meaningful if r["est"]) / len(meaningful)) if meaningful else float("nan"),
            "meaningful_interactions": len(meaningful),
            "scored": len(scored),
            "gmfe": 10 ** (sum(absl) / len(absl)) if absl else float("nan"),
            "within_1_25": within(1.25), "within_1_5": within(1.5), "within_2": within(2.0),
            "in_range": sum(in_range) / len(in_range) if in_range else float("nan"),
            "category_agreement": sum(cat) / len(cat) if cat else float("nan"),
            "under_predicted": sum(x < 1 / 2 for x in fe), "over_predicted": sum(x > 2 for x in fe),
            "worst": [(r["victim"], r["perpetrator"], round(r["observed"], 2), r["est"]["auc_ratio"],
                       "; ".join(r["sources"])) for r in scored[:20]],
            "missing": [(r["victim"], r["perpetrator"], round(r["observed"], 2)) for r in meaningful if not r["est"]][:20],
        }
    return results


def report(results: Dict[str, dict]) -> str:
    pct = lambda x: "n/a" if x != x else f"{100 * x:.1f}%"
    L = ["# PK exposure-estimate validation", "",
         "Engine estimates: basic static model with FDA class-calibrated parameters (see api/ddi/pk_model.py).", ""]
    for name, r in results.items():
        L += [f"## {name}", "", "| Metric | Value |", "|---|---|",
              f"| Observed pairs | {r['pairs']} ({r['meaningful_interactions']} with |AUCR change| >= 25%) |",
              f"| Coverage (engine gave an estimate for a meaningful interaction) | {pct(r['coverage'])} |",
              f"| Pairs scored | {r['scored']} |",
              f"| GMFE | {r['gmfe']:.2f} |" if r['gmfe'] == r['gmfe'] else "| GMFE | n/a |",
              f"| Within 1.25 / 1.5 / 2-fold | {pct(r['within_1_25'])} / {pct(r['within_1_5'])} / {pct(r['within_2'])} |",
              f"| Observed inside stated plausible range | {pct(r['in_range'])} |",
              f"| FDA magnitude category agreement | {pct(r['category_agreement'])} |",
              f"| Under- / over-predicted by > 2-fold | {r['under_predicted']} / {r['over_predicted']} |", ""]
        if r["worst"]:
            L += ["Largest disagreements (audit these first):", "",
                  "| Victim | Perpetrator | Observed | Predicted | Source |", "|---|---|---|---|---|"]
            L += [f"| {v} | {p} | {o} | {e} | {s} |" for v, p, o, e, s in r["worst"]] + [""]
        if r["missing"]:
            L += ["Observed interactions with no engine estimate: " +
                  ", ".join(f"{v} + {p} ({o}x)" for v, p, o in r["missing"]), ""]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reference", nargs="+", type=Path)
    ap.add_argument("--holdout-seed", type=int)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    rows = []
    for p in args.reference:
        with p.open(newline="", encoding="utf-8") as fh:
            rows += list(csv.DictReader(fh))
    if not rows:
        print("no reference rows", file=sys.stderr)
        return 1
    with isolated_engine():
        text = report(evaluate(rows, args.holdout_seed))
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
