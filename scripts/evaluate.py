"""Evaluate the engine against the internal gold standard and independent references.

Gold standard (``eval/gold_standard.csv``, authored by this project): a
regression set. It shows the rules fire; it does not show generalisation.

Independent references (``--reference FILE``, repeatable), built by
``scripts/references/*`` from sources this project did not author:

* DDInter (pharmacist-curated Major/Moderate/Minor)       -> scale ``ddinter``
* KEGG DDI (label-derived CI = contraindicated, P = precaution) -> scale ``kegg``
* ONC expert-panel high/low-priority lists                -> scale ``onc``

Circularity guard: the engine can *use* DDInter as an evidence layer and a
learned model as a signal layer. Both are switched off during evaluation, so
the engine is scored only on its own curated and mechanism layers.

Metrics per reference
* coverage: share of reference interactions for which the engine reports any
  finding (the "how often is it useful" ceiling)
* recall at or above the reference grade, per grade, with bootstrap 95% CIs
* exact agreement and quadratic-weighted kappa on a harmonised ordinal scale
* under-calls (engine lower) and gross under-calls (>= 2 grades lower)
* false-alert rate on reference negatives, when the reference has any

Usage::

    python -m scripts.evaluate [--reference eval/references/ddinter.csv] [--out eval/report.md]
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import os
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

os.environ.setdefault("DDI_ENABLE_RXNAV", "false")

from api.ddi import evidence, learned  # noqa: E402
from api.ddi.engine import SEVERITY_RANK, analyze_pair  # noqa: E402

FULL = ["None", "Minor", "Moderate", "Major", "Contraindicated"]
ENGINE_ORD = {"None known": 0, "Minor": 1, "Moderate": 2, "Major": 3, "Contraindicated": 4}


@contextlib.contextmanager
def isolated_engine():
    """Disable the external-evidence and learned layers for a fair evaluation."""
    saved = {k: os.environ.get(k) for k in ("DDI_DATA_DIR", "DDI_MODEL_PATH")}
    with tempfile.TemporaryDirectory() as empty:
        os.environ["DDI_DATA_DIR"] = empty
        os.environ.pop("DDI_MODEL_PATH", None)
        evidence.reload()
        learned.reload()
        try:
            yield
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            evidence.reload()
            learned.reload()


# --------------------------------------------------------------------------- statistics

def weighted_kappa(a: Sequence[int], b: Sequence[int], k: int = len(FULL)) -> float:
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


def bootstrap_ci(items: Sequence, stat: Callable[[Sequence], float], n: int = 1000, seed: int = 0):
    if not items:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    vals = sorted(stat([items[rng.randrange(len(items))] for _ in items]) for _ in range(n))
    vals = [v for v in vals if v == v]
    if not vals:
        return (float("nan"), float("nan"))
    return (vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))])


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


# --------------------------------------------------------------------------- gold standard

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


# --------------------------------------------------------------------------- independent references

def detect_scale(rows: List[dict]) -> str:
    sev = {r["severity"] for r in rows}
    if "Precaution" in sev or (sev and sev <= {"Contraindicated", "Precaution", "None"}):
        return "kegg"
    if any(r.get("source", "").startswith("ONC") for r in rows):
        return "onc"
    if "Contraindicated" not in sev:
        return "ddinter"
    return "full"


def _harmonise(sev: str, scale: str) -> Optional[int]:
    """Map a grade onto the reference's ordinal scale; None if not graded on it."""
    if sev in ("Unknown", "Precaution"):
        return None
    o = ENGINE_ORD.get(sev, FULL.index(sev) if sev in FULL else None)
    if o is None:
        return None
    if scale in ("ddinter", "onc"):  # these scales top out at Major
        o = min(o, 3)
    return o


def evaluate_reference(rows: List[dict], scale: Optional[str] = None) -> dict:
    scale = scale or detect_scale(rows)
    k = 4 if scale in ("ddinter", "onc") else 5
    records = []
    for r in rows:
        out = analyze_pair(r["drug1"], r["drug2"])
        records.append({"ref": r["severity"], "eng": out["severity"], "found": out["status"] == "interaction_found",
                         "drug1": r["drug1"], "drug2": r["drug2"]})

    positives = [x for x in records if x["ref"] != "None"]
    negatives = [x for x in records if x["ref"] == "None"]
    cov = lambda xs: _mean([float(x["found"]) for x in xs])

    by_level: Dict[str, dict] = {}
    for level in ("Contraindicated", "Major", "Moderate", "Minor", "Precaution", "Unknown"):
        xs = [x for x in records if x["ref"] == level]
        if not xs:
            continue
        entry = {"n": len(xs), "detected": cov(xs), "detected_ci": bootstrap_ci(xs, cov)}
        ref_o = _harmonise(level, scale)
        if ref_o is not None:
            at = lambda ys, ro=ref_o: _mean([float((_harmonise(y["eng"], scale) or 0) >= ro) for y in ys])
            entry["at_or_above"] = at(xs)
            entry["at_or_above_ci"] = bootstrap_ci(xs, at)
        if level == "Contraindicated":
            entry["engine_contraindicated"] = _mean([float(x["eng"] == "Contraindicated") for x in xs])
        by_level[level] = entry

    graded = [x for x in records if _harmonise(x["ref"], scale) is not None]
    graded_pos = [x for x in positives if x["ref"] != "Unknown"]
    pairs_o = [(_harmonise(x["ref"], scale), _harmonise(x["eng"], scale) or 0) for x in graded]
    kappa = lambda ps: weighted_kappa([a for a, _ in ps], [b for _, b in ps], k)
    # Reference Major/Contraindicated pairs the engine grades lower: the curation worklist.
    high = _harmonise("Major", scale)
    undergraded_high = [(x["drug1"], x["drug2"], x["ref"], x["eng"]) for x in graded
                        if (_harmonise(x["ref"], scale) or 0) >= high
                        and (_harmonise(x["eng"], scale) or 0) < (_harmonise(x["ref"], scale) or 0)]
    gross = [x for x, (a, b) in zip(graded, pairs_o) if a - b >= 2]
    return {
        "scale": scale,
        "pairs": len(records),
        "coverage": cov(positives),
        "coverage_ci": bootstrap_ci(positives, cov),
        "coverage_graded": cov(graded_pos),
        "coverage_graded_ci": bootstrap_ci(graded_pos, cov),
        "by_level": by_level,
        "graded_pairs": len(graded),
        "exact_agreement": _mean([float(a == b) for a, b in pairs_o]),
        # Kappa needs at least two reference grades (KEGG grades only CI, so it is undefined there).
        "weighted_kappa": kappa(pairs_o) if len({a for a, _ in pairs_o}) >= 2 else float("nan"),
        "weighted_kappa_ci": bootstrap_ci(pairs_o, kappa) if len({a for a, _ in pairs_o}) >= 2
        else (float("nan"), float("nan")),
        "under_calls": sum(b < a for a, b in pairs_o),
        "gross_under_calls": len(gross),
        "over_calls": sum(b > a for a, b in pairs_o),
        "false_alert_rate": cov(negatives) if negatives else None,
        "negatives": len(negatives),
        "worst_under_calls": [(x["drug1"], x["drug2"], x["ref"], x["eng"]) for x in gross[:25]],
        "missed_examples": [(x["drug1"], x["drug2"], x["ref"]) for x in positives if not x["found"]
                            and x["ref"] in ("Contraindicated", "Major")][:25],
        "undergraded_high": undergraded_high,
        "undergraded_by_drug": Counter(d for x in undergraded_high for d in (x[0], x[1])).most_common(30),
    }


# --------------------------------------------------------------------------- report

def _pct(x) -> str:
    return "n/a" if x is None or x != x else f"{100 * x:.1f}%"


def _ci(c) -> str:
    return "" if not c or c[0] != c[0] else f" ({_pct(c[0])}-{_pct(c[1])})"


def report(gold: dict, refs: Dict[str, dict]) -> str:
    L = ["# BioGPT-DDI evaluation report", "",
         "Engine evaluated with the external-evidence and learned layers disabled (no circularity).", "",
         "## 1. Internal gold standard (regression set, authored by this project)", "",
         "| Metric | Value |", "|---|---|",
         f"| Pairs | {gold['pairs']} |",
         f"| Safety-critical recall | {_pct(gold['critical_recall'])} |",
         f"| Interaction recall (at >= expected grade) | {_pct(gold['interaction_recall'])} |",
         f"| Under-call rate | {_pct(gold['under_call_rate'])} |",
         f"| False-alert rate | {_pct(gold['false_alert_rate'])} |",
         f"| Unrecognised input handled safely | {_pct(gold['unrecognized_handled'])} |", ""]
    if gold["misses"]:
        L += ["| Drug 1 | Drug 2 | Expected | Engine |", "|---|---|---|---|"]
        L += [f"| {a} | {b} | {e} | {g} |" for a, b, e, g in gold["misses"]] + [""]
    for i, (name, r) in enumerate(refs.items(), 2):
        L += [f"## {i}. Independent reference: {name} (scale: {r['scale']})", "",
              "| Metric | Value (95% bootstrap CI) |", "|---|---|",
              f"| Pairs (both drugs in lexicon) | {r['pairs']} |",
              f"| Coverage: interactions with any engine finding | {_pct(r['coverage'])}{_ci(r['coverage_ci'])} |",
              f"| Coverage excluding severity-'Unknown' records | {_pct(r['coverage_graded'])}"
              f"{_ci(r['coverage_graded_ci'])} |",
              f"| Graded pairs | {r['graded_pairs']} |",
              f"| Exact agreement | {_pct(r['exact_agreement'])} |",
              ("| Quadratic-weighted kappa | n/a (reference has a single grade) |"
               if r['weighted_kappa'] != r['weighted_kappa'] else
               f"| Quadratic-weighted kappa | {r['weighted_kappa']:.3f}"
               + (f" ({r['weighted_kappa_ci'][0]:.3f}-{r['weighted_kappa_ci'][1]:.3f})"
                  if r['weighted_kappa_ci'][0] == r['weighted_kappa_ci'][0] else "") + " |"),
              f"| Under-calls / gross under-calls (>= 2 grades) | {r['under_calls']} / {r['gross_under_calls']} |",
              f"| Over-calls | {r['over_calls']} |",
              f"| False-alert rate on negatives | {_pct(r['false_alert_rate'])} (n={r['negatives']}) |", "",
              "| Reference grade | n | Detected (any finding) | Engine at or above grade |", "|---|---|---|---|"]
        for level, e in r["by_level"].items():
            extra = f"; engine Contraindicated {_pct(e['engine_contraindicated'])}" if "engine_contraindicated" in e else ""
            L.append(f"| {level} | {e['n']} | {_pct(e['detected'])}{_ci(e['detected_ci'])} | "
                     f"{_pct(e.get('at_or_above'))}{_ci(e.get('at_or_above_ci'))}{extra} |")
        L.append("")
        if r["missed_examples"]:
            L += ["Missed high-severity pairs (first 25): " +
                  ", ".join(f"{a} + {b} ({s})" for a, b, s in r["missed_examples"]), ""]
        if r["undergraded_by_drug"]:
            L += [f"High-severity pairs graded lower by the engine: {len(r['undergraded_high'])}. "
                  "Drugs most often involved (curation worklist): " +
                  ", ".join(f"{d} ({n})" for d, n in r["undergraded_by_drug"]), ""]
        if r["worst_under_calls"]:
            L += ["Gross under-calls (first 25): " +
                  ", ".join(f"{a} + {b} (ref {s}, engine {e})" for a, b, s, e in r["worst_under_calls"]), ""]
    return "\n".join(L) + "\n"


def _read(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", type=Path, default=Path("eval/gold_standard.csv"))
    ap.add_argument("--reference", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--min-critical-recall", type=float, default=1.0,
                    help="exit non-zero if gold-standard safety-critical recall falls below this")
    args = ap.parse_args(argv)
    with isolated_engine():
        gold = evaluate_gold(_read(args.gold))
        refs = {}
        for p in args.reference:
            rows = _read(p)
            if rows:
                refs[p.stem] = evaluate_reference(rows)
            else:
                print(f"skipping empty reference {p}", file=sys.stderr)
    text = report(gold, refs)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if gold["critical_recall"] >= args.min_critical_recall else 1


if __name__ == "__main__":
    raise SystemExit(main())
