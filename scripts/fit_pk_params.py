"""Fit drug-specific CR-IR parameters on the calibration half of observed AUC ratios.

CR-IR method (Ohno Y et al., Clin Pharmacokinet 2007;46:681-96; Hisaka A et al., Pharmacol Ther
2009;121:85-109):

    inhibition:  AUCR = 1 / (1 - CR * IR)       (CR = fm of the victim, IR = inhibitory ratio of the perpetrator)
    induction:   AUCR = 1 / (1 + CR * IC)       (IC = induction capacity of the perpetrator)

Each observation (victim, perpetrator, AUCR) is assigned to the CYP enzyme through which the engine links the
two drugs. CR, IR and IC are estimated by alternating least squares, each shrunk towards its FDA class prior
(sensitive/moderate substrate, strong/moderate/weak perpetrator) so that drugs with few observations stay
close to the class value.

Only the calibration half is used (the same deterministic split as scripts/evaluate_pk.py --holdout-seed), so
the holdout half remains an honest test.

Usage::

    python -m scripts.fit_pk_params eval/references/pk_labels.csv --holdout-seed 7 [--out api/ddi/data/pk_crir.json]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

os.environ.setdefault("DDI_ENABLE_RXNAV", "false")

from api.ddi import pk_model  # noqa: E402
from api.ddi.lexicon import DRUGS  # noqa: E402
from scripts.evaluate_pk import _split  # noqa: E402

PRIOR_WEIGHT = 0.25
CR_BOUNDS, IR_BOUNDS, IC_BOUNDS = (0.05, 0.995), (0.05, 0.995), (0.1, 50.0)


def _clip(x: float, bounds: Tuple[float, float]) -> float:
    return max(bounds[0], min(bounds[1], x))


def link_enzyme(victim: str, perp: str, kind: str) -> Optional[str]:
    """The CYP enzyme connecting victim and perpetrator (CYP3A4 first, as the engine's largest effect usually is)."""
    v, p = DRUGS.get(victim), DRUGS.get(perp)
    if not v or not p:
        return None
    roles = p.inh if kind == "inhibit" else p.ind
    shared = [e for e in v.sub if e in roles and e in pk_model.CYP_ENZYMES]
    if not shared:
        return None
    return "CYP3A4" if "CYP3A4" in shared else sorted(shared)[0]


def collapse(rows: List[dict]) -> Dict[Tuple[str, str], float]:
    vals: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for r in rows:
        try:
            v = float(r["observed_aucr"])
        except (KeyError, TypeError, ValueError):
            continue
        if v > 0:
            vals[(r["victim"], r["perpetrator"])].append(v)
    return {k: math.exp(sum(map(math.log, vs)) / len(vs)) for k, vs in vals.items()}


def _link(obs: Dict[Tuple[str, str], float]):
    inh_obs, ind_obs = [], []  # (victim, perp, enzyme, target)
    for (victim, perp), aucr in obs.items():
        if aucr > 1.05:
            enz = link_enzyme(victim, perp, "inhibit")
            if enz:
                inh_obs.append((victim, perp, enz, 1 - 1 / aucr))
        elif aucr < 0.95:
            enz = link_enzyme(victim, perp, "induce")
            if enz:
                ind_obs.append((victim, perp, enz, 1 / aucr - 1))
    return inh_obs, ind_obs


def _priors(victim: str, perp: str, enz: str, kind: str):
    cr0 = pk_model.FM_SUBSTRATE[DRUGS[victim].sub[enz]][1]
    if kind == "inhibit":
        return cr0, 1 - 1 / pk_model.R_INHIBITOR[DRUGS[perp].inh[enz]][1]
    return cr0, pk_model.E_INDUCER.get(DRUGS[perp].ind[enz], pk_model.E_INDUCER["moderate"])[1] - 1


def predict(params: dict, victim: str, perp: str, enz: str, kind: str) -> float:
    """AUCR from fitted parameters, falling back to class priors (mirrors api/ddi/pk_model.py)."""
    cr0, x0 = _priors(victim, perp, enz, kind)
    cr = (params.get("cr", {}).get(victim, {}).get(enz) or {}).get("value", cr0)
    if kind == "inhibit":
        ir = (params.get("ir", {}).get(perp, {}).get(enz) or {}).get("value", x0)
        return 1 / (1 - cr * ir)
    ic = (params.get("ic", {}).get(perp, {}).get(enz) or {}).get("value", x0)
    return 1 / (1 + cr * ic)


def _fold(key: Tuple[str, str], k: int) -> int:
    import hashlib

    return hashlib.sha256(f"cv:{key[0]}|{key[1]}".encode()).digest()[0] % k


def cv_error(obs: Dict[Tuple[str, str], float], weight: Optional[float], k: int = 5) -> float:
    """Mean |ln(pred/obs)| over k-fold cross-validation inside the given (calibration) observations."""
    errs = []
    for f in range(k):
        train = {key: v for key, v in obs.items() if _fold(key, k) != f}
        test = {key: v for key, v in obs.items() if _fold(key, k) == f}
        params = fit(train, prior_weight=weight) if weight is not None else {}
        inh_t, ind_t = _link(test)
        for v, p, e, _ in inh_t:
            errs.append(abs(math.log(predict(params, v, p, e, "inhibit") / test[(v, p)])))
        for v, p, e, _ in ind_t:
            errs.append(abs(math.log(predict(params, v, p, e, "induce") / test[(v, p)])))
    return sum(errs) / len(errs) if errs else float("inf")


WEIGHT_GRID = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, None)  # None = no fitting (class priors only)


def select_weight(obs: Dict[Tuple[str, str], float]) -> Tuple[Optional[float], Dict[str, float]]:
    scores = {("class" if w is None else str(w)): cv_error(obs, w) for w in WEIGHT_GRID}
    best_w, best = None, scores["class"]
    for w in WEIGHT_GRID[:-1]:  # a fitted weight must strictly beat the class model to be used
        if scores[str(w)] < best - 1e-9:
            best_w, best = w, scores[str(w)]
    return best_w, scores


def fit(obs: Dict[Tuple[str, str], float], prior_weight: float = PRIOR_WEIGHT, iterations: int = 50) -> dict:
    inh_obs, ind_obs = _link(obs)

    cr0, ir0, ic0 = {}, {}, {}
    for v, _p, e, _ in inh_obs + ind_obs:
        cr0[(v, e)] = pk_model.FM_SUBSTRATE[DRUGS[v].sub[e]][1]
    for _v, p, e, _ in inh_obs:
        ir0[(p, e)] = 1 - 1 / pk_model.R_INHIBITOR[DRUGS[p].inh[e]][1]
    for _v, p, e, _ in ind_obs:
        level = DRUGS[p].ind[e]
        ic0[(p, e)] = pk_model.E_INDUCER.get(level, pk_model.E_INDUCER["moderate"])[1] - 1
    cr, ir, ic = dict(cr0), dict(ir0), dict(ic0)

    for _ in range(iterations):
        num, den = defaultdict(float), defaultdict(float)
        for v, p, e, t in inh_obs:
            num[(v, e)] += t * ir[(p, e)]
            den[(v, e)] += ir[(p, e)] ** 2
        for v, p, e, u in ind_obs:
            num[(v, e)] += u * ic[(p, e)]
            den[(v, e)] += ic[(p, e)] ** 2
        for k in cr:
            cr[k] = _clip((num[k] + prior_weight * cr0[k]) / (den[k] + prior_weight), CR_BOUNDS)
        num, den = defaultdict(float), defaultdict(float)
        for v, p, e, t in inh_obs:
            num[(p, e)] += t * cr[(v, e)]
            den[(p, e)] += cr[(v, e)] ** 2
        for k in ir:
            ir[k] = _clip((num[k] + prior_weight * ir0[k]) / (den[k] + prior_weight), IR_BOUNDS)
        num, den = defaultdict(float), defaultdict(float)
        for v, p, e, u in ind_obs:
            num[(p, e)] += u * cr[(v, e)]
            den[(p, e)] += cr[(v, e)] ** 2
        for k in ic:
            ic[k] = _clip((num[k] + prior_weight * ic0[k]) / (den[k] + prior_weight), IC_BOUNDS)

    counts = defaultdict(int)
    for v, p, e, _ in inh_obs + ind_obs:
        counts[("cr", v, e)] += 1
        counts[("ir" if (p, e) in ir else "ic", p, e)] += 1

    def table(name: str, values: dict) -> dict:
        out: Dict[str, Dict[str, dict]] = defaultdict(dict)
        for (drug, enz), val in sorted(values.items()):
            out[drug][enz] = {"value": round(val, 4), "n": counts[(name, drug, enz)]}
        return dict(out)

    return {"method": "CR-IR alternating least squares with FDA class priors", "prior_weight": prior_weight,
            "n_inhibition": len(inh_obs), "n_induction": len(ind_obs),
            "cr": table("cr", cr), "ir": table("ir", ir), "ic": table("ic", ic)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reference", nargs="+", type=Path)
    ap.add_argument("--holdout-seed", type=int, required=True,
                    help="fit only on the calibration half of this split (must match evaluate_pk)")
    ap.add_argument("--out", type=Path, default=pk_model.DEFAULT_PARAMS)
    args = ap.parse_args(argv)
    rows = []
    for p in args.reference:
        with p.open(newline="", encoding="utf-8") as fh:
            rows += list(csv.DictReader(fh))
    obs = {k: v for k, v in collapse(rows).items() if _split(*k, args.holdout_seed) == "calibration"}
    weight, scores = select_weight(obs)
    if weight is None:
        inh_obs, ind_obs = _link(obs)
        params = {"method": "class priors retained: no fitted shrinkage beat them in cross-validation",
                  "prior_weight": None, "n_inhibition": len(inh_obs), "n_induction": len(ind_obs),
                  "cr": {}, "ir": {}, "ic": {}}
    else:
        params = fit(obs, prior_weight=weight)
    params.update({"fitted_on": f"calibration half, seed {args.holdout_seed}", "pairs": len(obs),
                   "cv_mean_abs_log_error": {k: round(v, 4) for k, v in scores.items()},
                   "retrieved": date.today().isoformat()})
    print("5-fold CV (mean |ln error|) by prior weight: " +
          ", ".join(f"{k}={v:.3f}" for k, v in scores.items()) + f" -> selected {weight or 'class priors'}",
          file=sys.stderr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(params, indent=1, sort_keys=True), encoding="utf-8")
    print(f"fitted on {len(obs)} calibration pairs ({params['n_inhibition']} inhibition, "
          f"{params['n_induction']} induction): CR for {len(params['cr'])} victims, IR for {len(params['ir'])} "
          f"inhibitors, IC for {len(params['ic'])} inducers -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
