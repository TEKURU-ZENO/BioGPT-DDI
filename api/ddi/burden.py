"""Regimen-level cumulative risk ("burden") scores.

Pairwise checks miss risks that only emerge across a whole medication list,
for example three mildly anticholinergic drugs or four CNS-active drugs in an
older adult. This module scores the regimen as a whole.

Sources
* Anticholinergic Cognitive Burden (ACB) scale - Boustani M et al., Aging
  Health 2008;4:311-20 and the 2012 update (Aging Brain Care). A total score
  >= 3 is associated with cognitive impairment and increased mortality.
  Scores here are transcribed for the ingredients in this knowledge base and
  should be verified by a pharmacist before clinical use.
* 2023 American Geriatrics Society Beers Criteria: avoid any combination of
  >= 3 CNS-active drugs (antiepileptics, antidepressants, antipsychotics,
  benzodiazepines, Z-drugs, opioids, skeletal muscle relaxants) in adults >= 65.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .lexicon import DrugProfile

ACB_SCORES: Dict[str, int] = {
    # score 3 - definite, strong anticholinergic activity
    "amitriptyline": 3, "clomipramine": 3, "nortriptyline": 3, "paroxetine": 3, "clozapine": 3,
    "olanzapine": 3, "quetiapine": 3, "chlorpromazine": 3, "diphenhydramine": 3, "hydroxyzine": 3,
    # score 2
    "carbamazepine": 2, "cyclobenzaprine": 2, "meperidine": 2,
    # score 1 - possible anticholinergic activity
    "alprazolam": 1, "atenolol": 1, "bupropion": 1, "captopril": 1, "chlorthalidone": 1, "codeine": 1,
    "colchicine": 1, "diazepam": 1, "digoxin": 1, "dipyridamole": 1, "fentanyl": 1, "fluvoxamine": 1,
    "furosemide": 1, "haloperidol": 1, "isosorbide mononitrate": 1, "isosorbide dinitrate": 1,
    "metoprolol": 1, "morphine": 1, "nifedipine": 1, "quinidine": 1, "theophylline": 1, "trazodone": 1,
    "triamterene": 1, "venlafaxine": 1, "warfarin": 1,
}

BEERS_CNS_TAGS = ("antiepileptic", "gabapentinoid", "ssri", "snri", "tca", "maoi", "antipsychotic",
                  "benzodiazepine", "z_drug", "opioid", "muscle_relaxant")
BEERS_CNS_EXTRA = {"trazodone", "mirtazapine", "bupropion"}  # antidepressants without a class tag
BLEEDING_TAGS = ("anticoagulant", "antiplatelet", "nsaid", "bleeding_serotonergic")
POTASSIUM_TAGS = ("raas", "k_sparing", "k_retaining", "potassium")


def _with(profiles: Sequence[DrugProfile], pred) -> List[str]:
    return sorted({p.name.title() for p in profiles if pred(p)})


def regimen_burden(profiles: Sequence[DrugProfile], age: Optional[float] = None) -> dict:
    """Score a list of ingredient profiles (duplicates are collapsed)."""
    uniq = list({p.name: p for p in profiles}.values())

    acb_contrib = {p.name.title(): ACB_SCORES[p.name] for p in uniq if p.name in ACB_SCORES}
    acb_total = sum(acb_contrib.values())
    qt = _with(uniq, lambda p: p.has("qt_known"))
    sero = _with(uniq, lambda p: p.has("serotonergic"))
    cns = _with(uniq, lambda p: any(p.has(t) for t in BEERS_CNS_TAGS) or p.name in BEERS_CNS_EXTRA)
    bleed = _with(uniq, lambda p: any(p.has(t) for t in BLEEDING_TAGS))
    potassium = _with(uniq, lambda p: any(p.has(t) for t in POTASSIUM_TAGS))

    alerts: List[dict] = []
    if acb_total >= 3:
        alerts.append({
            "level": "warning", "axis": "anticholinergic",
            "message": f"Anticholinergic burden score {acb_total} (>= 3): associated with cognitive impairment, "
                       f"falls and mortality, particularly in older adults. Consider deprescribing the "
                       f"highest-scoring agents.",
            "source": "Anticholinergic Cognitive Burden scale (Boustani 2008; 2012 update)"})
    if len(qt) >= 2:
        alerts.append({
            "level": "critical" if len(qt) >= 3 else "warning", "axis": "qt",
            "message": f"{len(qt)} drugs with known torsades de pointes risk ({', '.join(qt)}). Obtain an ECG, "
                       f"correct potassium/magnesium and minimise the number of QT-prolonging agents.",
            "source": "CredibleMeds QTdrugs list"})
    if len(sero) >= 3:
        alerts.append({
            "level": "warning", "axis": "serotonin",
            "message": f"{len(sero)} serotonergic drugs ({', '.join(sero)}): cumulative serotonin toxicity risk.",
            "source": "Boyer & Shannon, N Engl J Med 2005"})
    if len(cns) >= 3:
        older = age is not None and age >= 65
        alerts.append({
            "level": "critical" if older else "warning", "axis": "cns",
            "message": f"{len(cns)} CNS-active drugs ({', '.join(cns)}). "
                       + ("Beers Criteria: avoid >= 3 CNS-active drugs in adults >= 65 (falls and fractures)."
                          if older else "In adults >= 65 the Beers Criteria advise avoiding >= 3 CNS-active "
                                        "drugs (falls and fractures)."),
            "source": "2023 AGS Beers Criteria"})
    if len(bleed) >= 3:
        alerts.append({
            "level": "warning", "axis": "bleeding",
            "message": f"{len(bleed)} drugs that increase bleeding risk ({', '.join(bleed)}). Review necessity "
                       f"and consider gastroprotection.",
            "source": "Product labeling"})
    if len(potassium) >= 3:
        alerts.append({
            "level": "warning", "axis": "potassium",
            "message": f"{len(potassium)} drugs that raise serum potassium ({', '.join(potassium)}). Monitor "
                       f"potassium and renal function.",
            "source": "Product labeling"})

    return {
        "anticholinergic": {"total": acb_total, "contributors": acb_contrib},
        "qt_known_risk": qt,
        "serotonergic": sero,
        "cns_active": cns,
        "bleeding_risk": bleed,
        "potassium_raising": potassium,
        "alerts": alerts,
    }
