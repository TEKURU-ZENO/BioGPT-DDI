"""Drug-gene and drug-drug-gene interactions, including phenoconversion.

A patient's *genetic* metabolizer phenotype (from genotyping) can be shifted
by co-medication: a strong CYP2D6 inhibitor makes a genetic normal
metabolizer behave like a poor metabolizer ("phenoconversion"). Prescribing
recommendations should use the resulting *functional* phenotype.

Conversion rules (Klomp SD et al., J Clin Med 2020;9:2890 - systematic review
of phenoconversion; consistent with CPIC/DPWG practice):

* strong inhibitor   -> functional poor metabolizer (PM)
* moderate inhibitor -> one step lower on the gene's scale (e.g. NM->IM, IM->PM)
* weak inhibitor     -> no change (noted)
* strong inducer     -> one step higher (CYP2C19 / CYP2C9 only; CYP2D6 is not
                        meaningfully inducible)

Drug-gene recommendations summarise CPIC guidelines (and DPWG where noted).
They are deliberately brief: consult the full guideline before acting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .lexicon import CYP2C9, CYP2C19, CYP2D6, DrugProfile

GENES = (CYP2D6, CYP2C19, CYP2C9)
ORDER = ["PM", "IM", "NM", "RM", "UM"]
VALID = {CYP2D6: {"PM", "IM", "NM", "UM"}, CYP2C19: {"PM", "IM", "NM", "RM", "UM"}, CYP2C9: {"PM", "IM", "NM"}}
NAMES = {"PM": "poor", "IM": "intermediate", "NM": "normal", "RM": "rapid", "UM": "ultrarapid"}
SRC_PHENOCONVERSION = "Klomp SD et al. Phenoconversion of cytochrome P450 metabolism: a systematic review. J Clin Med 2020"


def _shift(pheno: str, steps: int, gene: str) -> str:
    """Move ``steps`` positions along the gene's phenotype scale (negative = less function)."""
    valid = [p for p in ORDER if p in VALID[gene]]
    idx = max(0, min(len(valid) - 1, valid.index(pheno) + steps))
    return valid[idx]


@dataclass
class GenePhenotype:
    gene: str
    genetic: str
    functional: str
    converted_by: List[str]

    def to_dict(self) -> dict:
        return {"gene": self.gene, "genetic": self.genetic, "functional": self.functional,
                "converted_by": self.converted_by,
                "phenoconverted": self.genetic != self.functional}


def functional_phenotypes(pgx: Dict[str, str], profiles: Sequence[DrugProfile]) -> Dict[str, GenePhenotype]:
    """Apply phenoconversion from co-medications to genotype-derived phenotypes."""
    out: Dict[str, GenePhenotype] = {}
    for gene, pheno in (pgx or {}).items():
        if gene not in VALID or pheno not in VALID[gene]:
            continue
        functional, by = pheno, []
        strengths = {p.name: p.inh.get(gene) for p in profiles if p.inh.get(gene)}
        if any(s == "strong" for s in strengths.values()):
            functional = "PM"
            by = [n.title() for n, s in strengths.items() if s == "strong"]
        elif any(s == "moderate" for s in strengths.values()):
            functional = _shift(pheno, -1, gene)
            by = [n.title() for n, s in strengths.items() if s == "moderate"]
        elif gene != CYP2D6:
            inducers = [p.name.title() for p in profiles if p.ind.get(gene) == "strong"]
            if inducers:
                functional, by = _shift(pheno, +1, gene), inducers
        out[gene] = GenePhenotype(gene, pheno, functional, by if functional != pheno else [])
    return out


# drug -> gene -> {phenotype: (level, recommendation)}
_RULES: Dict[str, Dict[str, Dict[str, tuple]]] = {
    "codeine": {CYP2D6: {
        "PM": ("critical", "Avoid codeine: greatly reduced conversion to morphine and lack of analgesia. "
                           "Use a non-tramadol alternative (e.g., morphine or a non-opioid)."),
        "UM": ("critical", "Avoid codeine: increased morphine formation and risk of serious toxicity "
                           "(respiratory depression). Use a non-tramadol alternative."),
        "IM": ("info", "Use label-recommended dosing; if no response, consider a non-tramadol opioid.")}},
    "tramadol": {CYP2D6: {
        "PM": ("warning", "Avoid tramadol: diminished analgesia. Use a non-codeine alternative."),
        "UM": ("critical", "Avoid tramadol: increased active-metabolite (O-desmethyltramadol) exposure and "
                           "toxicity risk. Use a non-codeine alternative."),
        "IM": ("info", "Use label-recommended dosing; if no response, consider a non-codeine opioid.")}},
    "tamoxifen": {CYP2D6: {
        "PM": ("critical", "Low endoxifen formation and higher recurrence risk. Consider an aromatase inhibitor "
                           "(post-menopausal, or pre-menopausal with ovarian suppression) or tamoxifen 40 mg/day. "
                           "Avoid CYP2D6 inhibitors."),
        "IM": ("warning", "Consider an aromatase inhibitor where appropriate, or tamoxifen 40 mg/day. Avoid "
                          "moderate/strong CYP2D6 inhibitors.")}},
    "ondansetron": {CYP2D6: {
        "UM": ("warning", "Increased metabolism and reduced antiemetic response. Select an alternative not "
                          "predominantly metabolised by CYP2D6 (e.g., granisetron).")}},
    "amitriptyline": {CYP2D6: {
        "PM": ("warning", "Avoid amitriptyline (higher exposure and side effects). If needed, start at 50% of the "
                          "usual dose and use therapeutic drug monitoring."),
        "UM": ("warning", "Avoid amitriptyline (risk of reduced efficacy). If needed, titrate with therapeutic "
                          "drug monitoring."),
        "IM": ("info", "Consider a 25% reduction of the starting dose.")},
        CYP2C19: {
        "PM": ("warning", "Avoid amitriptyline. If needed, start at 50% of the usual dose with therapeutic drug "
                          "monitoring."),
        "UM": ("warning", "Avoid amitriptyline (altered parent/metabolite ratio)."),
        "RM": ("warning", "Avoid amitriptyline (altered parent/metabolite ratio).")}},
    "nortriptyline": {CYP2D6: {
        "PM": ("warning", "Avoid nortriptyline. If needed, start at 50% of the usual dose with therapeutic drug "
                          "monitoring."),
        "UM": ("warning", "Avoid nortriptyline (risk of reduced efficacy)."),
        "IM": ("info", "Consider a 25% reduction of the starting dose.")}},
    "paroxetine": {CYP2D6: {
        "PM": ("warning", "Consider a lower starting dose and slower titration (about 50% of the usual "
                          "maintenance dose)."),
        "UM": ("warning", "Select an alternative not predominantly metabolised by CYP2D6.")}},
    "metoprolol": {CYP2D6: {
        "PM": ("info", "Higher metoprolol exposure and greater heart-rate lowering. Start low and titrate in "
                       "smaller steps by response (DPWG).")}},
    "flecainide": {CYP2D6: {
        "PM": ("warning", "Reduce the dose by about 50% and monitor ECG and plasma concentrations (DPWG).")}},
    "clopidogrel": {CYP2C19: {
        "PM": ("critical", "Avoid clopidogrel: minimal active-metabolite formation and increased risk of major "
                           "adverse cardiovascular events. Use prasugrel or ticagrelor if not contraindicated."),
        "IM": ("warning", "Reduced clopidogrel effect. For ACS/PCI and neurovascular indications, avoid standard-"
                          "dose clopidogrel and use prasugrel or ticagrelor if not contraindicated.")}},
    "citalopram": {CYP2C19: {
        "PM": ("warning", "Consider a 50% reduction of the starting dose (max 20 mg/day; QT risk)."),
        "UM": ("warning", "Consider an alternative not predominantly metabolised by CYP2C19."),
        "RM": ("info", "Standard starting dose; if no response, consider an alternative.")}},
    "escitalopram": {CYP2C19: {
        "PM": ("warning", "Consider a 50% reduction of the starting dose and slower titration."),
        "UM": ("warning", "Consider an alternative not predominantly metabolised by CYP2C19."),
        "RM": ("info", "Standard starting dose; if no response, consider an alternative.")}},
    "sertraline": {CYP2C19: {
        "PM": ("info", "Consider a lower starting dose and slower titration (about 50% lower maintenance dose).")}},
    "omeprazole": {CYP2C19: {
        "UM": ("warning", "Increase the starting daily dose by 100% (risk of therapeutic failure)."),
        "PM": ("info", "Standard starting dose; for chronic therapy (>12 weeks) consider a 50% dose reduction."),
        "IM": ("info", "Standard starting dose; for chronic therapy (>12 weeks) consider a 50% dose reduction.")}},
    "lansoprazole": {CYP2C19: {
        "UM": ("warning", "Increase the starting daily dose by 100% (risk of therapeutic failure)."),
        "PM": ("info", "Standard starting dose; for chronic therapy (>12 weeks) consider a 50% dose reduction.")}},
    "pantoprazole": {CYP2C19: {
        "UM": ("warning", "Increase the starting daily dose by 100% (risk of therapeutic failure)."),
        "PM": ("info", "Standard starting dose; for chronic therapy (>12 weeks) consider a 50% dose reduction.")}},
    "voriconazole": {CYP2C19: {
        "UM": ("critical", "Subtherapeutic voriconazole concentrations are likely. Choose an alternative agent "
                           "(e.g., isavuconazole, liposomal amphotericin B or posaconazole)."),
        "RM": ("warning", "Subtherapeutic concentrations are possible. Choose an alternative agent."),
        "PM": ("warning", "Higher concentrations and toxicity risk. Choose an alternative, or use a reduced dose "
                          "with therapeutic drug monitoring.")}},
    "warfarin": {CYP2C9: {
        "IM": ("warning", "Reduced warfarin dose requirement. Use a validated pharmacogenetic dosing algorithm "
                          "(including VKORC1) and monitor INR closely."),
        "PM": ("critical", "Substantially reduced warfarin dose requirement and higher bleeding risk. Use a "
                           "pharmacogenetic dosing algorithm (including VKORC1) and monitor INR closely.")}},
    "phenytoin": {CYP2C9: {
        "IM": ("warning", "Consider a 25% reduction of the starting maintenance dose; use therapeutic drug "
                          "monitoring. (Also check HLA-B*15:02 status.)"),
        "PM": ("warning", "Consider a 50% reduction of the starting maintenance dose; use therapeutic drug "
                          "monitoring. (Also check HLA-B*15:02 status.)")}},
    "celecoxib": {CYP2C9: {
        "IM": ("info", "Initiate at the lowest recommended starting dose."),
        "PM": ("warning", "Initiate at 25-50% of the lowest recommended starting dose, or choose an alternative "
                          "not metabolised by CYP2C9.")}},
    "ibuprofen": {CYP2C9: {
        "IM": ("info", "Initiate at the lowest recommended starting dose."),
        "PM": ("warning", "Initiate at 25-50% of the lowest recommended starting dose, or choose an alternative.")}},
    "meloxicam": {CYP2C9: {
        "IM": ("warning", "Initiate at 50% of the lowest recommended starting dose, or choose an alternative."),
        "PM": ("critical", "Choose an alternative NSAID not metabolised by CYP2C9 (markedly prolonged half-life).")}},
    "piroxicam": {CYP2C9: {
        "PM": ("critical", "Choose an alternative NSAID not metabolised by CYP2C9 (markedly prolonged half-life).")}},
}

_SOURCES = {
    "codeine": "CPIC guideline for CYP2D6, OPRM1, COMT and opioids (2021)",
    "tramadol": "CPIC guideline for CYP2D6, OPRM1, COMT and opioids (2021)",
    "tamoxifen": "CPIC guideline for CYP2D6 and tamoxifen (2018)",
    "ondansetron": "CPIC guideline for CYP2D6 and ondansetron/tropisetron (2017)",
    "amitriptyline": "CPIC guideline for CYP2D6, CYP2C19 and tricyclic antidepressants (2016)",
    "nortriptyline": "CPIC guideline for CYP2D6, CYP2C19 and tricyclic antidepressants (2016)",
    "paroxetine": "CPIC guideline for CYP2D6, CYP2C19, CYP2B6, SLC6A4, HTR2A and antidepressants (2023)",
    "citalopram": "CPIC guideline for CYP2D6, CYP2C19, CYP2B6, SLC6A4, HTR2A and antidepressants (2023)",
    "escitalopram": "CPIC guideline for CYP2D6, CYP2C19, CYP2B6, SLC6A4, HTR2A and antidepressants (2023)",
    "sertraline": "CPIC guideline for CYP2D6, CYP2C19, CYP2B6, SLC6A4, HTR2A and antidepressants (2023)",
    "metoprolol": "DPWG guideline: CYP2D6 and metoprolol",
    "flecainide": "DPWG guideline: CYP2D6 and flecainide",
    "clopidogrel": "CPIC guideline for CYP2C19 and clopidogrel (2022)",
    "omeprazole": "CPIC guideline for CYP2C19 and proton pump inhibitors (2020)",
    "lansoprazole": "CPIC guideline for CYP2C19 and proton pump inhibitors (2020)",
    "pantoprazole": "CPIC guideline for CYP2C19 and proton pump inhibitors (2020)",
    "voriconazole": "CPIC guideline for CYP2C19 and voriconazole (2016)",
    "warfarin": "CPIC guideline for pharmacogenetics-guided warfarin dosing (2017)",
    "phenytoin": "CPIC guideline for CYP2C9, HLA-B and phenytoin (2020)",
    "celecoxib": "CPIC guideline for CYP2C9 and NSAIDs (2020)",
    "ibuprofen": "CPIC guideline for CYP2C9 and NSAIDs (2020)",
    "meloxicam": "CPIC guideline for CYP2C9 and NSAIDs (2020)",
    "piroxicam": "CPIC guideline for CYP2C9 and NSAIDs (2020)",
}


def drug_gene_alerts(profiles: Sequence[DrugProfile], pgx: Dict[str, str]) -> List[dict]:
    """CPIC/DPWG recommendations using each drug's functional phenotype.

    A drug never phenoconverts itself: recommendations for e.g. paroxetine or
    omeprazole are genotype-based even though both inhibit their own pathway,
    so each drug's functional phenotype is computed from the *other* drugs only.
    """
    alerts: List[dict] = []
    uniq = list({x.name: x for x in profiles}.values())
    for p in uniq:
        if p.name not in _RULES:
            continue
        phenos = functional_phenotypes(pgx, [q for q in uniq if q.name != p.name])
        for gene, table in _RULES[p.name].items():
            gp = phenos.get(gene)
            if not gp or gp.functional not in table:
                continue
            level, rec = table[gp.functional]
            converted = gp.functional != gp.genetic
            how = (f"functional {NAMES[gp.functional]} metabolizer (genetic {NAMES[gp.genetic]} metabolizer, "
                   f"phenoconverted by {', '.join(gp.converted_by)})" if converted
                   else f"{NAMES[gp.functional]} metabolizer")
            alerts.append({
                "category": "drug-drug-gene" if converted else "drug-gene",
                "level": level,
                "drug": p.name.title(),
                "gene": gene,
                "title": f"{p.name.title()}: {gene} {gp.functional}" + (" (phenoconversion)" if converted else ""),
                "message": f"Patient is a {gene} {how}. {rec}",
                "source": _SOURCES.get(p.name, "CPIC") + (f"; {SRC_PHENOCONVERSION}" if converted else ""),
            })
    return alerts


def ddi_genotype_note(enzyme: str, phenos: Dict[str, GenePhenotype]) -> Optional[str]:
    """Explain how genotype changes the size of an enzyme-mediated DDI."""
    gp = phenos.get(enzyme)
    if not gp:
        return None
    if gp.genetic == "PM":
        return (f"Patient is a genetic {enzyme} poor metabolizer: the inhibitor adds little further effect on this "
                f"pathway, but baseline exposure of the substrate is already elevated (drug-gene interaction).")
    if gp.genetic == "UM":
        return (f"Patient is a {enzyme} ultrarapid metabolizer: the relative impact of inhibition may be larger "
                f"than average.")
    return None
