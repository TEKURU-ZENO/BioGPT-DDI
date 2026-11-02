"""Patient context: renal function, age and pharmacogenomics.

Patient factors change both single-drug appropriateness and the clinical
weight of an interaction. This module produces

* patient alerts for individual drugs (renal dosing thresholds, Beers
  Criteria for adults >= 65, CPIC drug-gene recommendations), and
* documented severity escalations of interaction findings (e.g. NSAID + ACE
  inhibitor in a patient with eGFR < 60).

Renal thresholds are taken from US product labeling and are stated against
eGFR. Several labels specify Cockcroft-Gault creatinine clearance instead;
the two are not interchangeable, particularly in older or low-weight
patients, and the alerts say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import pgx as pgx_mod
from .lexicon import DrugProfile

SRC_BEERS = "2023 American Geriatrics Society Beers Criteria"
CRCL_NOTE = " (label threshold is creatinine clearance; eGFR used as an approximation)"


@dataclass
class Patient:
    age: Optional[float] = None
    egfr: Optional[float] = None
    pgx: Dict[str, str] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.age is None and self.egfr is None and not self.pgx


# (ingredient, below_egfr, level, message, uses_crcl)
_RENAL = [
    ("metformin", 30, "critical", "Contraindicated when eGFR < 30.", False),
    ("metformin", 45, "warning", "Do not initiate when eGFR is 30-45; reassess benefit/risk if eGFR falls below 45.",
     False),
    ("dabigatran", 15, "critical", "Not recommended (CrCl < 15).", True),
    ("dabigatran", 30, "warning", "Atrial fibrillation: reduce to 75 mg twice daily (CrCl 15-30).", True),
    ("rivaroxaban", 15, "critical", "Avoid (CrCl < 15).", True),
    ("rivaroxaban", 50, "warning", "Atrial fibrillation: reduce to 15 mg once daily (CrCl 15-50).", True),
    ("edoxaban", 15, "critical", "Not recommended (CrCl < 15).", True),
    ("edoxaban", 50, "warning", "Reduce to 30 mg once daily (CrCl 15-50).", True),
    ("enoxaparin", 30, "warning", "Dose adjustment required (CrCl < 30).", True),
    ("dofetilide", 20, "critical", "Contraindicated (CrCl < 20).", True),
    ("dofetilide", 60, "warning", "Reduce dose (CrCl 20-60) and monitor QTc.", True),
    ("sotalol", 40, "critical", "Sotalol for atrial fibrillation is contraindicated when CrCl < 40.", True),
    ("eplerenone", 30, "critical", "Contraindicated (CrCl <= 30): hyperkalaemia.", True),
    ("spironolactone", 30, "warning", "Avoid when eGFR < 30 (hyperkalaemia).", False),
    ("potassium chloride", 30, "warning", "Use with caution: impaired potassium excretion.", False),
    ("methotrexate", 30, "critical", "Avoid in severe renal impairment.", True),
    ("methotrexate", 60, "warning", "Reduce dose and monitor for toxicity.", True),
    ("colchicine", 30, "warning", "Reduce dose and avoid repeat courses more often than every 14 days; "
                                  "contraindicated with P-gp or strong CYP3A4 inhibitors.", True),
    ("lithium", 60, "warning", "Reduced lithium clearance: lower doses and more frequent level monitoring.", False),
    ("digoxin", 50, "warning", "Reduced clearance: lower maintenance dose and monitor levels.", True),
    ("gabapentin", 60, "warning", "Reduce dose (CrCl < 60).", True),
    ("pregabalin", 60, "warning", "Reduce dose (CrCl < 60).", True),
    ("sitagliptin", 30, "warning", "Reduce to 25 mg once daily (eGFR < 30).", False),
    ("sitagliptin", 45, "info", "Reduce to 50 mg once daily (eGFR 30-45).", False),
    ("glyburide", 60, "warning", "Avoid in CKD (prolonged hypoglycaemia); prefer glipizide if a sulfonylurea is "
                                 "needed.", False),
    ("morphine", 30, "warning", "Accumulation of active metabolites: avoid or use reduced doses.", False),
    ("codeine", 30, "warning", "Accumulation of active metabolites: avoid.", False),
    ("tramadol", 30, "warning", "Extend dosing interval to every 12 h; maximum 200 mg/day.", True),
    ("trimethoprim", 30, "warning", "Halve the dose; increased hyperkalaemia risk.", True),
    ("ciprofloxacin", 50, "info", "Dose adjustment may be required.", True),
    ("levofloxacin", 50, "info", "Dose adjustment required.", True),
    ("famotidine", 60, "info", "Reduce dose (risk of CNS adverse effects).", True),
    ("levetiracetam", 50, "info", "Dose adjustment required.", True),
]
_NSAID_RENAL = (30, "warning", "Avoid NSAIDs when eGFR < 30 (acute kidney injury, hyperkalaemia).")

# Beers 2023 - ingredient or tag selector -> (level, message)
_BEERS = [
    ("@benzodiazepine", "warning", "Avoid: increased risk of cognitive impairment, delirium, falls and fractures."),
    ("@z_drug", "warning", "Avoid: minimal benefit; delirium, falls and fractures."),
    ("diphenhydramine", "warning", "Avoid: strongly anticholinergic (confusion, constipation, urinary retention)."),
    ("hydroxyzine", "warning", "Avoid: strongly anticholinergic."),
    ("amitriptyline", "warning", "Avoid: strongly anticholinergic, sedating, orthostatic hypotension."),
    ("clomipramine", "warning", "Avoid: strongly anticholinergic, sedating, orthostatic hypotension."),
    ("nortriptyline", "warning", "Avoid: anticholinergic, sedating, orthostatic hypotension."),
    ("paroxetine", "warning", "Avoid: strongly anticholinergic among SSRIs."),
    ("cyclobenzaprine", "warning", "Avoid: anticholinergic, sedation, fracture risk; questionable efficacy."),
    ("carisoprodol", "warning", "Avoid: anticholinergic, sedation, fracture risk."),
    ("meperidine", "warning", "Avoid: oral meperidine is ineffective at usual doses and may cause neurotoxicity."),
    ("@sulfonylurea", "warning", "Avoid as first- or second-line therapy: hypoglycaemia; if needed, short-acting "
                                 "glipizide is preferred."),
    ("indomethacin", "warning", "Avoid: highest risk of GI bleeding and CNS adverse effects among NSAIDs."),
    ("ketorolac", "warning", "Avoid: GI bleeding and acute kidney injury."),
    ("@nsaid", "info", "Avoid chronic use unless alternatives are ineffective and a PPI is co-prescribed."),
    ("@antipsychotic", "info", "Avoid except for schizophrenia, bipolar disorder or short-term antiemetic use: "
                               "increased stroke and mortality in dementia."),
    ("nifedipine", "info", "Avoid immediate-release nifedipine: hypotension and myocardial ischaemia."),
    ("amiodarone", "info", "Avoid as first-line therapy for atrial fibrillation unless heart failure or LVH."),
    ("digoxin", "info", "Avoid as first-line therapy for AF or heart failure; avoid doses > 0.125 mg/day."),
    ("warfarin", "info", "Avoid starting warfarin as initial therapy for VTE or non-valvular AF unless DOACs are "
                         "contraindicated."),
    ("rivaroxaban", "info", "Use with caution for long-term AF/VTE treatment: higher bleeding risk than apixaban."),
    ("dabigatran", "info", "Use with caution: higher GI bleeding risk than warfarin in adults >= 75."),
    ("aspirin", "info", "Avoid initiating for primary prevention of cardiovascular disease."),
    ("@ppi", "info", "Avoid scheduled use for > 8 weeks unless clearly indicated (C. difficile, bone loss, "
                     "fractures)."),
]


def _sel(sel: str, p: DrugProfile) -> bool:
    return p.has(sel[1:]) if sel.startswith("@") else p.name == sel


def renal_alerts(profiles: Sequence[DrugProfile], egfr: float) -> List[dict]:
    alerts: List[dict] = []
    for p in {x.name: x for x in profiles}.values():
        rules = sorted((r for r in _RENAL if r[0] == p.name), key=lambda r: r[1])
        for name, below, level, msg, crcl in rules:  # most severe threshold that applies wins
            if egfr < below:
                alerts.append({"category": "renal", "level": level, "drug": p.name.title(),
                               "title": f"{p.name.title()}: renal dose check (eGFR {egfr:g})",
                               "message": msg + (CRCL_NOTE if crcl else ""),
                               "source": f"{p.name.title()} US Prescribing Information"})
                break
        if p.has("nsaid") and egfr < _NSAID_RENAL[0]:
            alerts.append({"category": "renal", "level": _NSAID_RENAL[1], "drug": p.name.title(),
                           "title": f"{p.name.title()}: avoid in severe renal impairment",
                           "message": _NSAID_RENAL[2], "source": SRC_BEERS})
    return alerts


def age_alerts(profiles: Sequence[DrugProfile], age: float) -> List[dict]:
    if age < 65:
        return []
    alerts: List[dict] = []
    for p in {x.name: x for x in profiles}.values():
        for sel, level, msg in _BEERS:  # first matching (most specific) entry wins
            if _sel(sel, p):
                alerts.append({"category": "age", "level": level, "drug": p.name.title(),
                               "title": f"{p.name.title()}: potentially inappropriate in adults >= 65",
                               "message": msg, "source": SRC_BEERS})
                break
    return alerts


def patient_alerts(profiles: Sequence[DrugProfile], patient: Patient) -> dict:
    alerts: List[dict] = []
    if patient.egfr is not None:
        alerts += renal_alerts(profiles, patient.egfr)
    if patient.age is not None:
        alerts += age_alerts(profiles, patient.age)
    phenos = pgx_mod.functional_phenotypes(patient.pgx, profiles)
    alerts += pgx_mod.drug_gene_alerts(profiles, patient.pgx)
    rank = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: rank[a["level"]])
    return {"alerts": alerts, "phenotypes": {g: p.to_dict() for g, p in phenos.items()}, "_phenos": phenos}


# --------------------------------------------------------------------------- escalation

def escalate(findings: List[dict], patient: Patient, phenos: Dict[str, "pgx_mod.GenePhenotype"]) -> None:
    """Adjust finding severities in place for patient factors (documented, never silent)."""
    egfr = patient.egfr
    for f in findings:
        axis, sev = f["axis"], f["severity"]
        new, why = None, None
        if egfr is not None:
            if axis == "potassium" and sev == "Moderate" and egfr < 45:
                new, why = "Major", f"eGFR {egfr:g} < 45 substantially increases hyperkalaemia risk."
            elif axis == "renal_nsaid" and sev == "Moderate" and egfr < 60:
                new, why = "Major", f"eGFR {egfr:g} < 60: higher risk of NSAID-associated acute kidney injury."
            elif "Colchicine" in f["drugs"] and f["basis"] == "curated" and "pk" in axis and egfr < 60 \
                    and sev != "Contraindicated":
                new, why = ("Contraindicated", "Colchicine with P-gp/strong CYP3A4 inhibitors is contraindicated "
                                               "in renal impairment (label).")
            elif axis == "curated:lithium,renal_nsaid" and egfr < 60:
                why = f"eGFR {egfr:g} < 60 further reduces lithium clearance; monitor levels closely."
        if new:
            f["escalated_from"], f["severity"] = sev, new
        if why:
            f.setdefault("patient_notes", []).append(why)
        enz = axis.split(":", 1)[1] if axis.startswith("inhibit:") else None
        note = pgx_mod.ddi_genotype_note(enz, phenos) if enz else None
        if note:
            f.setdefault("patient_notes", []).append(note)
