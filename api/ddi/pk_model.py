"""Class-based static mechanistic model of exposure change (AUC ratio).

Basic static model (FDA In Vitro / Clinical DDI guidance, 2020):

    inhibition:  AUCR = 1 / ( fm / R + (1 - fm) )
    induction:   AUCR = 1 / ( fm * E + (1 - fm) )

* ``fm`` - fraction of the victim's clearance via the affected enzyme.
* ``R``  - fold-reduction of that enzyme's activity by the inhibitor.
* ``E``  - fold-increase of that enzyme's activity by the inducer.

Drug-specific Ki, [I] and fm values are not yet curated, so parameters come
from the FDA classification categories that the lexicon already encodes:

* FDA defines a *strong* inhibitor as raising a sensitive index substrate's
  AUC >= 5-fold, *moderate* 2- to <5-fold and *weak* 1.25- to <2-fold. With
  fm ~ 1 these map to R >= 5, 2-5 and 1.25-2.
* A *sensitive* substrate shows >= 5-fold AUC increase with a strong
  inhibitor (fm >= ~0.8); a *moderate* substrate 2- to <5-fold (fm ~ 0.5-0.8).
* Strong / moderate / weak inducers decrease a sensitive substrate's AUC by
  >= 80% / 50-80% / 20-50%, giving E >= 5, 2-5 and 1.25-2.

The output is an order-of-magnitude estimate with a range, not a prediction
for an individual patient. Transporter (P-gp) effects are not modelled
because they lack an equivalent class-level calibration.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

R_INHIBITOR = {"strong": (5.0, 10.0, 20.0), "moderate": (2.0, 3.0, 5.0), "weak": (1.25, 1.5, 2.0)}
E_INDUCER = {"strong": (5.0, 7.0, 10.0), "moderate": (2.0, 3.0, 5.0), "weak": (1.25, 1.5, 2.0)}
FM_SUBSTRATE = {"sensitive": (0.8, 0.9, 0.95), "moderate": (0.5, 0.65, 0.8)}

MODEL_NAME = "Basic static model, FDA class-calibrated parameters"
FITTED_MODEL_NAME = "CR-IR static model with drug-specific parameters fitted on FDA-label observations"
DEFAULT_PARAMS = Path(__file__).resolve().parent / "data" / "pk_crir.json"


@lru_cache(maxsize=1)
def fitted_params() -> dict:
    """Drug-specific CR (victim) / IR, IC (perpetrator) values from scripts/fit_pk_params.py, if available.

    CR-IR method (Ohno et al., Clin Pharmacokinet 2007; Hisaka et al., Pharmacol Ther 2009):
    inhibition AUCR = 1 / (1 - CR * IR), induction AUCR = 1 / (1 + CR * IC). CR equals fm, IR = 1 - 1/R and
    IC = E - 1 in this module's notation, so class-level values are the special case of no fitted parameter.
    """
    if os.getenv("DDI_DISABLE_PK_FIT", "").lower() in {"1", "true", "yes"}:
        return {}
    path = Path(os.getenv("DDI_PK_PARAMS") or DEFAULT_PARAMS)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def reload() -> None:
    fitted_params.cache_clear()


def _fitted(table: str, drug: Optional[str], enzyme: str) -> Optional[float]:
    entry = (fitted_params().get(table) or {}).get(drug or "", {}).get(enzyme)
    return float(entry["value"]) if entry else None
CYP_ENZYMES = {"CYP3A4", "CYP2C9", "CYP2C19", "CYP2D6", "CYP1A2", "CYP2C8", "CYP2B6"}


def _aucr_inh(fm: float, r: float) -> float:
    return 1.0 / (fm / r + (1.0 - fm))


def _aucr_ind(fm: float, e: float) -> float:
    return 1.0 / (fm * e + (1.0 - fm))


def _fmt(x: float) -> str:
    return f"{x:.1f}" if x < 10 else f"{x:.0f}"


def estimate(kind: str, enzyme: str, strength: str, sensitivity: str,
             victim: Optional[str] = None, perpetrator: Optional[str] = None) -> Optional[dict]:
    """Return an AUC-ratio estimate for an inhibition/induction finding, or None.

    Drug-specific fitted parameters (if loaded) replace the class midpoints for the point estimate; the plausible
    range stays class-based and is widened to include the point.
    """
    if enzyme not in CYP_ENZYMES or sensitivity not in FM_SUBSTRATE:
        return None
    fm_lo, fm_mid, fm_hi = FM_SUBSTRATE[sensitivity]
    cr = _fitted("cr", victim, enzyme)
    used = []
    if cr is not None:
        fm_mid = cr
        used.append(f"{victim} CR {cr:.2f}")
    if kind == "inhibit":
        if strength not in R_INHIBITOR:
            return None
        r_lo, r_mid, r_hi = R_INHIBITOR[strength]
        ir = _fitted("ir", perpetrator, enzyme)
        if ir is not None:
            r_mid = 1 / (1 - ir)
            used.append(f"{perpetrator} IR {ir:.2f}")
        point, lo, hi = _aucr_inh(fm_mid, r_mid), _aucr_inh(fm_lo, r_lo), _aucr_inh(fm_hi, r_hi)
        lo, hi = min(lo, point), max(hi, point)
        summary = f"~{_fmt(point)}-fold increase in AUC (plausible range {_fmt(lo)}-{_fmt(hi)}x)"
    elif kind == "induce":
        if strength not in E_INDUCER:
            return None
        e_lo, e_mid, e_hi = E_INDUCER[strength]
        ic = _fitted("ic", perpetrator, enzyme)
        if ic is not None:
            e_mid = 1 + ic
            used.append(f"{perpetrator} IC {ic:.2f}")
        point, lo, hi = _aucr_ind(fm_mid, e_mid), _aucr_ind(fm_lo, e_lo), _aucr_ind(fm_hi, e_hi)
        lo, hi = min(lo, hi, point), max(lo, hi, point)
        summary = (f"~{round((1 - point) * 100)}% decrease in AUC "
                   f"(plausible range {round((1 - hi) * 100)}-{round((1 - lo) * 100)}%)")
    else:
        return None
    basis = ("Drug-specific parameters: " + ", ".join(used) + " (fitted on FDA-label observations); "
             if used else "Class-level estimate; ")
    return {
        "model": FITTED_MODEL_NAME if used else MODEL_NAME,
        "auc_ratio": round(point, 2),
        "auc_ratio_range": [round(lo, 2), round(hi, 2)],
        "summary": summary,
        "assumptions": f"{strength} {enzyme} {'inhibitor' if kind == 'inhibit' else 'inducer'}; "
                       f"{sensitivity} {enzyme} substrate (class fm {FM_SUBSTRATE[sensitivity][0]}-"
                       f"{FM_SUBSTRATE[sensitivity][2]}). {basis}dose, formulation and patient factors not modelled.",
    }
