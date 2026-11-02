"""Interaction engine.

Layer A - curated rules (:mod:`api.ddi.rules`): label/regulatory-backed.
Layer B - mechanism engine (this module): infers interactions from each
          ingredient's CYP/P-gp roles and pharmacodynamic risk axes.

Severity is decided only by these deterministic layers, never by a language
model. An empty result is reported as "no known interaction in this knowledge
base", which is not the same as "safe".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import evidence
from . import learned, pk_model
from .burden import regimen_burden
from .patient import Patient, escalate, patient_alerts
from .lexicon import DRUGS, KB_VERSION, SYNONYMS, DrugProfile
from .normalize import ResolvedDrug, resolve
from .rules import (CONTRAINDICATED, CURATED, MAJOR, MINOR, MODERATE, PD, PK, SRC_CREDIBLEMEDS,
                    SRC_FDA_CYP, SRC_GABA_DSC, SRC_LINEZOLID_DSC, SRC_OPI_BZD_DSC, SRC_SEROTONIN, Rule)

SEVERITY_RANK = {CONTRAINDICATED: 4, MAJOR: 3, MODERATE: 2, MINOR: 1}
UNKNOWN, NONE_KNOWN = "Unknown", "None known"

DISCLAIMER = (
    "For education and research only. Not a substitute for professional medical advice or a licensed clinical "
    "interaction database. The knowledge base covers a limited set of drugs; the absence of an alert does not "
    "mean a combination is safe. Never start, stop or change a medicine without consulting a clinician or "
    "pharmacist."
)


@dataclass
class Finding:
    severity: str
    category: str
    axis: str
    title: str
    mechanism: str
    effect: str
    management: str
    patient_summary: str
    watch_for: List[str]
    evidence: List[str]
    basis: str  # "curated" | "mechanism-inferred" | "duplication"
    evidence_level: str
    drugs: Tuple[str, str]
    pk_estimate: Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["drugs"] = [x.title() for x in self.drugs]
        return d


# --------------------------------------------------------------------------- helpers

def _sel_match(sel: str, drug: DrugProfile) -> bool:
    return drug.has(sel[1:]) if sel.startswith("@") else drug.name == sel


def _rule_matches(rule: Rule, x: DrugProfile, y: DrugProfile) -> bool:
    fwd = any(_sel_match(s, x) for s in rule.a) and any(_sel_match(s, y) for s in rule.b)
    rev = any(_sel_match(s, y) for s in rule.a) and any(_sel_match(s, x) for s in rule.b)
    return fwd or rev


def _covered(axis: str, covers: Iterable[str]) -> bool:
    covers = set(covers)
    family = axis.split(":")[0]
    if family in {"inhibit", "induce", "prodrug"}:
        family = "pk"
    return axis in covers or family in covers


def _f(sev, cat, axis, title, mech, effect, mgmt, patient, watch, evidence, basis, level, x, y) -> Finding:
    return Finding(sev, cat, axis, title, mech, effect, mgmt, patient, list(watch), list(evidence), basis, level,
                   (x.name, y.name))


_PK_LEVEL = "Mechanism-inferred (FDA index-drug classification)"
_EXT_LEVEL = "External database (not independently curated)"
_PD_LEVEL = "Mechanism-inferred (pharmacodynamic class effect)"
_CURATED_LEVEL = "Established (product labeling / regulatory guidance)"


# --------------------------------------------------------------------------- layer B: PK

def _inhibition_severity(strength: str, sensitivity: str, nti: bool) -> Optional[str]:
    if strength == "strong":
        return MAJOR if (sensitivity == "sensitive" or nti) else MODERATE
    if strength == "moderate":
        if nti:
            return MAJOR
        return MODERATE if sensitivity == "sensitive" else MINOR
    if strength == "weak" and nti:
        return MINOR
    return None


def _induction_severity(strength: str, sensitivity: str, nti: bool) -> Optional[str]:
    if strength == "strong":
        return MAJOR if (sensitivity == "sensitive" or nti) else MODERATE
    if strength == "moderate":
        return MODERATE if (sensitivity == "sensitive" or nti) else MINOR
    return None


def _pk_findings(perp: DrugProfile, victim: DrugProfile) -> List[Finding]:
    out: List[Finding] = []
    for enz, strength in perp.inh.items():
        if enz in victim.sub:
            sev = _inhibition_severity(strength, victim.sub[enz], victim.nti)
            if sev:
                nti_txt = " It has a narrow therapeutic index." if victim.nti else ""
                out.append(_f(
                    sev, PK, f"inhibit:{enz}",
                    f"{perp.name.title()} increases {victim.name.title()} exposure ({enz} inhibition)",
                    f"{perp.name.title()} is a {strength} {enz} inhibitor; {victim.name.title()} is a "
                    f"{victim.sub[enz]} {enz} substrate.{nti_txt}",
                    f"Higher {victim.name.title()} concentrations and an increased risk of dose-related adverse effects.",
                    f"Consider an alternative to {perp.name.title()} or reduce the {victim.name.title()} dose; "
                    f"monitor clinical response{' and drug levels' if victim.nti else ''}.",
                    f"{perp.name.title()} can raise the amount of {victim.name.title()} in your body, which may "
                    f"increase its side effects.",
                    (f"more side effects from {victim.name.title()} than usual",),
                    (SRC_FDA_CYP,), "mechanism-inferred", _PK_LEVEL, perp, victim))
                out[-1].pk_estimate = pk_model.estimate("inhibit", enz, strength, victim.sub[enz])
        if victim.prodrug == enz and strength in {"strong", "moderate"}:
            out.append(_f(
                MODERATE, PK, f"prodrug:{enz}",
                f"{perp.name.title()} may reduce activation of {victim.name.title()} ({enz})",
                f"{victim.name.title()} is a prodrug activated by {enz}; {perp.name.title()} is a {strength} "
                f"{enz} inhibitor.",
                f"Reduced formation of the active metabolite and potentially reduced efficacy of {victim.name.title()}.",
                f"Consider an alternative without {enz} inhibition or monitor for reduced therapeutic effect.",
                f"{perp.name.title()} may make {victim.name.title()} work less well.",
                (f"{victim.name.title()} seeming not to work as well as before",),
                (SRC_FDA_CYP,), "mechanism-inferred", _PK_LEVEL, perp, victim))
    for enz, strength in perp.ind.items():
        if enz in victim.sub:
            sev = _induction_severity(strength, victim.sub[enz], victim.nti)
            if sev:
                out.append(_f(
                    sev, PK, f"induce:{enz}",
                    f"{perp.name.title()} decreases {victim.name.title()} exposure ({enz} induction)",
                    f"{perp.name.title()} is a {strength} {enz} inducer; {victim.name.title()} is a "
                    f"{victim.sub[enz]} {enz} substrate.",
                    f"Lower {victim.name.title()} concentrations and possible loss of efficacy; levels may rise "
                    f"again when {perp.name.title()} is stopped.",
                    f"Avoid if possible; otherwise monitor efficacy{' and drug levels' if victim.nti else ''} and "
                    f"adjust the dose when starting or stopping {perp.name.title()}.",
                    f"{perp.name.title()} can lower the amount of {victim.name.title()} in your body, so it may "
                    f"not work as well.",
                    (f"{victim.name.title()} seeming not to work as well as before",),
                    (SRC_FDA_CYP,), "mechanism-inferred", _PK_LEVEL, perp, victim))
                out[-1].pk_estimate = pk_model.estimate("induce", enz, strength, victim.sub[enz])
    return out


# --------------------------------------------------------------------------- layer B: PD

def _either(x: DrugProfile, y: DrugProfile, tx, ty) -> bool:
    def m(d, t):
        return any(d.has(tag) for tag in ((t,) if isinstance(t, str) else t))
    return (m(x, tx) and m(y, ty)) or (m(y, tx) and m(x, ty))


SEROTONIN_WATCH = ("agitation, restlessness or confusion", "fast heartbeat", "high fever or heavy sweating",
                   "muscle twitching, jerking or stiffness", "diarrhoea")
BLEED_WATCH = ("unusual bruising", "bleeding gums or nosebleeds", "black, tarry stools or blood in urine",
               "vomiting blood")
CNS_WATCH = ("extreme sleepiness or difficulty waking", "slow or shallow breathing", "confusion",
             "dizziness or falls")


def _pd_findings(x: DrugProfile, y: DrugProfile) -> List[Finding]:
    out: List[Finding] = []
    add = lambda *a: out.append(_f(*a, "mechanism-inferred", _PD_LEVEL, x, y))

    # serotonin toxicity
    if _either(x, y, "maoi", "serotonergic"):
        add(CONTRAINDICATED, PD, "serotonin", "MAO inhibitor with a serotonergic drug",
            "MAO inhibition blocks serotonin breakdown while the other drug increases serotonergic transmission.",
            "Serotonin syndrome, which can be life-threatening (hyperthermia, clonus, autonomic instability).",
            "Contraindicated. Observe the required washout (generally 14 days after an MAOI; 5 weeks after fluoxetine).",
            "These must not be taken together because they can cause a life-threatening reaction called serotonin "
            "syndrome.", SEROTONIN_WATCH, (SRC_LINEZOLID_DSC, SRC_SEROTONIN))
    elif x.has("serotonergic") and y.has("serotonergic"):
        add(MODERATE, PD, "serotonin", "Additive serotonergic effect",
            "Both drugs increase serotonergic activity.",
            "Increased risk of serotonin syndrome, particularly when starting or increasing a dose.",
            "Use the combination only if clinically justified; start low, titrate slowly and counsel on symptoms.",
            "Together these can increase serotonin levels and, rarely, cause serotonin syndrome.",
            SEROTONIN_WATCH, (SRC_SEROTONIN,))

    # QT prolongation
    if x.has("qt_known") and y.has("qt_known"):
        add(MAJOR, PD, "qt", "Additive QT prolongation / torsades de pointes",
            "Both drugs are in the 'known risk of TdP' category (hERG / IKr blockade).",
            "QT prolongation with risk of torsades de pointes and sudden cardiac death; risk is higher with "
            "hypokalaemia, hypomagnesaemia, bradycardia, female sex, structural heart disease and high doses.",
            "Avoid if an alternative exists. Otherwise obtain a baseline ECG, correct potassium/magnesium and "
            "monitor the QTc.",
            "Both medicines can affect your heart rhythm, and the risk is higher when they are taken together.",
            ("fainting", "palpitations or a racing/irregular heartbeat", "seizures"), (SRC_CREDIBLEMEDS,))

    # CNS / respiratory depression
    if _either(x, y, "opioid", ("benzodiazepine", "z_drug", "barbiturate", "alcohol", "gabapentinoid",
                                "cns_depressant")):
        src = (SRC_OPI_BZD_DSC, SRC_GABA_DSC) if _either(x, y, "opioid", "gabapentinoid") else (SRC_OPI_BZD_DSC,)
        add(MAJOR, PD, "cns", "Opioid with another CNS depressant",
            "Additive depression of the central nervous system and brainstem respiratory drive.",
            "Profound sedation, respiratory depression, coma and death.",
            "Avoid unless alternatives are inadequate; use the lowest doses for the shortest duration, monitor "
            "for sedation and respiratory depression, and consider prescribing naloxone.",
            "Taking these together can cause dangerous drowsiness and slowed breathing, which can be fatal.",
            CNS_WATCH, src)
    elif _either(x, y, ("benzodiazepine", "z_drug", "barbiturate"), "alcohol"):
        add(MAJOR, PD, "cns", "Sedative-hypnotic with alcohol",
            "Additive GABA-A-mediated CNS depression.",
            "Excessive sedation, impaired psychomotor function, respiratory depression.",
            "Advise avoiding alcohol.",
            "Do not drink alcohol with this medicine; together they can cause dangerous drowsiness and slowed breathing.",
            CNS_WATCH, ("Benzodiazepine / Z-drug US Prescribing Information",))
    elif x.has("cns_depressant") and y.has("cns_depressant"):
        add(MODERATE, PD, "cns", "Additive CNS depression",
            "Both drugs depress the central nervous system.",
            "Increased drowsiness, dizziness, psychomotor impairment and fall risk (especially in older adults).",
            "Use the lowest effective doses; counsel against driving until the effect is known.",
            "Together these can make you very drowsy or dizzy.", CNS_WATCH, (SRC_GABA_DSC,)
            if _either(x, y, "gabapentinoid", "cns_depressant") else ())

    # bleeding
    if x.has("anticoagulant") and y.has("anticoagulant"):
        add(MAJOR, PD, "bleeding", "Two anticoagulants",
            "Additive anticoagulation.",
            "High risk of major bleeding.",
            "Avoid concurrent use except during a supervised transition between agents.",
            "Taking two blood thinners together greatly increases the risk of serious bleeding.",
            BLEED_WATCH, ("Anticoagulant US Prescribing Information",))
    elif _either(x, y, "anticoagulant", ("antiplatelet", "nsaid")):
        add(MAJOR, PD, "bleeding", "Anticoagulant with an antiplatelet/NSAID",
            "Additive impairment of haemostasis; NSAIDs also injure the gastrointestinal mucosa.",
            "Substantially increased risk of major and gastrointestinal bleeding.",
            "Avoid NSAIDs. Combine with antiplatelets only for a defined indication, for the shortest duration, "
            "with gastroprotection.",
            "Taking these together increases the risk of serious bleeding.",
            BLEED_WATCH, ("Anticoagulant US Prescribing Information",))
    elif _either(x, y, "anticoagulant", "bleeding_serotonergic"):
        add(MODERATE, PD, "bleeding", "Anticoagulant with an SSRI/SNRI",
            "SSRIs/SNRIs deplete platelet serotonin, impairing platelet aggregation.",
            "Increased bleeding risk.",
            "Monitor for bleeding; consider gastroprotection in patients at high GI risk.",
            "This combination can slightly increase your risk of bleeding.",
            BLEED_WATCH, ("SSRI/SNRI US Prescribing Information (abnormal bleeding)",))
    elif _either(x, y, ("antiplatelet", "bleeding_serotonergic"), "nsaid") or \
            _either(x, y, "bleeding_serotonergic", "antiplatelet"):
        extra = (" Ibuprofen and naproxen can also block the cardioprotective effect of low-dose aspirin if taken "
                 "before it." if _either(x, y, "salicylate", "nsaid") else "")
        add(MODERATE, PD, "bleeding", "Additive bleeding risk",
            "Additive effects on platelet function and/or gastrointestinal mucosa." + extra,
            "Increased risk of gastrointestinal bleeding.",
            "Use the lowest effective doses for the shortest time; consider a PPI in patients at high GI risk.",
            "Together these can increase the risk of stomach bleeding.",
            BLEED_WATCH, ("SSRI/SNRI and NSAID US Prescribing Information",))
    elif x.has("antiplatelet") and y.has("antiplatelet"):
        add(MODERATE, PD, "bleeding", "Dual antiplatelet therapy",
            "Additive platelet inhibition.",
            "Increased bleeding risk. Often intentional (e.g., after ACS or stenting).",
            "Confirm the indication and planned duration; consider PPI gastroprotection (not omeprazole/esomeprazole "
            "with clopidogrel).",
            "These are sometimes prescribed together on purpose, but they increase bleeding risk.",
            BLEED_WATCH, ("ACC/AHA guidance on dual antiplatelet therapy",))
    elif x.has("nsaid") and y.has("nsaid"):
        add(MODERATE, PD, "bleeding", "Two NSAIDs (duplication)",
            "Duplicate COX inhibition without added benefit.",
            "Increased gastrointestinal bleeding and renal toxicity.",
            "Avoid using two NSAIDs together.",
            "These are both anti-inflammatory painkillers; taking two together increases side effects without "
            "extra benefit.", BLEED_WATCH, ("NSAID US Prescribing Information",))

    # potassium
    if _either(x, y, "k_sparing", "potassium"):
        add(MAJOR, PD, "potassium", "Hyperkalaemia: potassium-sparing diuretic with potassium supplement",
            "Reduced renal potassium excretion combined with potassium loading.",
            "Severe hyperkalaemia and cardiac arrhythmia.",
            "Avoid unless serum potassium is documented to be low and closely monitored.",
            "This combination can raise potassium in your blood to dangerous levels.",
            ("muscle weakness", "slow or irregular heartbeat", "numbness or tingling"),
            ("Aldactone (spironolactone) US Prescribing Information",))
    elif _either(x, y, "raas", ("k_retaining", "potassium")):
        add(MODERATE, PD, "potassium", "Hyperkalaemia risk",
            "RAAS blockade reduces aldosterone-mediated potassium excretion; the other drug retains or adds potassium.",
            "Hyperkalaemia, especially with renal impairment, diabetes, older age or dehydration.",
            "Check potassium and creatinine at baseline and within 1 week of starting; avoid potassium supplements "
            "unless indicated.",
            "This combination can raise the potassium level in your blood; you may need blood tests.",
            ("muscle weakness", "slow or irregular heartbeat"), ("ACE inhibitor / ARB US Prescribing Information",))

    # dual RAAS blockade
    if x.has("raas") and y.has("raas"):
        same_class = (x.has("acei") and y.has("acei")) or (x.has("arb") and y.has("arb"))
        if same_class:
            add(MODERATE, PD, "raas", "Therapeutic duplication within the same RAAS class",
                "Two agents with the same mechanism.",
                "Hypotension, hyperkalaemia and renal impairment without added benefit.",
                "Use a single agent.",
                "These two medicines work the same way; taking both is usually not needed.",
                ("dizziness", "reduced urine output"), ())
        else:
            add(MAJOR, PD, "raas", "Dual renin-angiotensin-aldosterone system blockade",
                "Combined inhibition at two points of the RAAS.",
                "Hyperkalaemia, hypotension and acute kidney injury without cardiovascular benefit "
                "(ONTARGET, VA NEPHRON-D).",
                "Avoid. Aliskiren with an ACE inhibitor or ARB is contraindicated in patients with diabetes.",
                "Taking these together can harm your kidneys and raise potassium without extra benefit.",
                ("dizziness or fainting", "reduced urine output", "muscle weakness"),
                ("ONTARGET (N Engl J Med 2008)", "VA NEPHRON-D (N Engl J Med 2013)",
                 "Tekturna (aliskiren) US Prescribing Information"))

    # NSAID + RAAS (renal / antihypertensive)
    if _either(x, y, "raas", "nsaid"):
        add(MODERATE, PD, "renal_nsaid", "NSAID with an ACE inhibitor/ARB",
            "NSAIDs inhibit renal prostaglandins, reducing afferent arteriolar dilation while RAAS blockade reduces "
            "efferent constriction; NSAIDs also cause sodium retention.",
            "Reduced antihypertensive effect and risk of acute kidney injury (higher still if a diuretic is also "
            "used - the 'triple whammy').",
            "Prefer acetaminophen. If an NSAID is necessary, use briefly, keep the patient hydrated and check renal "
            "function.",
            "Anti-inflammatory painkillers can make your blood pressure medicine work less well and can harm the "
            "kidneys.", ("reduced urine output", "swelling of legs or ankles"),
            ("NSAID and ACE inhibitor/ARB US Prescribing Information",))

    # hypotension
    if _either(x, y, "pde5_inhibitor", "alpha_blocker"):
        add(MODERATE, PD, "hypotension", "PDE5 inhibitor with an alpha-blocker",
            "Additive vasodilation.",
            "Symptomatic (orthostatic) hypotension.",
            "Ensure the patient is stable on the alpha-blocker first; start the PDE5 inhibitor at the lowest dose.",
            "Together these can lower your blood pressure and make you dizzy when standing up.",
            ("dizziness or light-headedness", "fainting"), ("PDE5 inhibitor US Prescribing Information",))

    # bradycardia / AV block
    if _either(x, y, "beta_blocker", "nondhp_ccb"):
        add(MAJOR, PD, "bradycardia", "Beta-blocker with verapamil/diltiazem",
            "Additive negative chronotropic and dromotropic effects on the SA and AV nodes, and additive negative "
            "inotropy.",
            "Severe bradycardia, AV block, hypotension and heart failure.",
            "Avoid, particularly with IV administration or pre-existing conduction disease / LV dysfunction. If used, "
            "monitor heart rate, blood pressure and ECG.",
            "Together these can slow your heart too much.",
            ("very slow pulse", "dizziness or fainting", "shortness of breath", "unusual tiredness"),
            ("Calan (verapamil) US Prescribing Information",))
    elif _either(x, y, "cardiac_glycoside", ("beta_blocker", "nondhp_ccb")):
        add(MODERATE, PD, "bradycardia", "Additive bradycardia with digoxin",
            "Additive slowing of AV-nodal conduction.",
            "Bradycardia and AV block.",
            "Monitor heart rate and ECG.",
            "Together these can slow your heart rate.",
            ("very slow pulse", "dizziness or fainting"), ("Lanoxin (digoxin) US Prescribing Information",))
    elif x.has("beta_blocker") and y.has("beta_blocker"):
        add(MODERATE, PD, "bradycardia", "Two beta-blockers (duplication)",
            "Duplicate beta-adrenergic blockade.", "Bradycardia and hypotension.",
            "Use a single beta-blocker.", "These two medicines work the same way; taking both is usually not needed.",
            ("very slow pulse", "dizziness"), ())

    # hypoglycaemia with alcohol
    if _either(x, y, "hypoglycemic", "alcohol"):
        add(MODERATE, PD, "hypoglycemia", "Hypoglycaemia with alcohol",
            "Alcohol inhibits hepatic gluconeogenesis and masks hypoglycaemia symptoms.",
            "Delayed and prolonged hypoglycaemia.",
            "Counsel to limit alcohol, never drink on an empty stomach and monitor glucose.",
            "Alcohol can cause low blood sugar with this medicine, sometimes hours later.",
            ("shakiness, sweating, fast heartbeat", "confusion"), ("Sulfonylurea / insulin US Prescribing Information",))

    # chelation / absorption
    if _either(x, y, ("fluoroquinolone", "tetracycline", "chelation_sensitive"), "polyvalent_cation"):
        add(MODERATE, PK, "chelation", "Reduced absorption due to chelation/binding",
            "Di- and trivalent cations (calcium, iron, magnesium, aluminium) bind the drug in the gut.",
            "Markedly reduced absorption and possible treatment failure.",
            "Separate doses: take the affected drug at least 2 hours before or 4-6 hours after the mineral/antacid "
            "(levothyroxine: 4 hours apart).",
            "Take these at different times of day; together, one stops the other from being absorbed.",
            ("the medicine not seeming to work",), ("Fluoroquinolone, tetracycline and levothyroxine US Prescribing "
                                                    "Information",))
    return out


# --------------------------------------------------------------------------- aggregation

def _pair_findings(x: DrugProfile, y: DrugProfile) -> List[Finding]:
    if x.name == y.name:
        return [_f(MAJOR, "Therapeutic duplication", "duplication",
                   f"Same active ingredient: {x.name.title()}",
                   "Both products contain the same active ingredient.",
                   "Unintentional double dosing and dose-related toxicity (e.g., acetaminophen liver injury).",
                   "Use only one product containing this ingredient and check the total daily dose.",
                   f"Both medicines contain {x.name.title()}. Taking both could mean taking too much.",
                   ("any side effects of overdose for this medicine",), ("Product labeling",),
                   "duplication", "Established (identical ingredient)", x, y)]

    findings: List[Finding] = []
    covers: set = set()
    for rule in CURATED:
        if _rule_matches(rule, x, y):
            axis = "curated:" + ",".join(rule.covers) if rule.covers else "curated"
            findings.append(_f(rule.severity, rule.category, axis, rule.title, rule.mechanism, rule.effect,
                               rule.management, rule.patient, rule.watch, rule.evidence, "curated",
                               _CURATED_LEVEL, x, y))
            covers.update(rule.covers)

    inferred = _pk_findings(x, y) + _pk_findings(y, x) + _pd_findings(x, y)
    seen_axes = set()
    for f in inferred:
        if _covered(f.axis, covers) or f.axis in seen_axes:
            continue
        seen_axes.add(f.axis)
        findings.append(f)
    return findings


_BRANDS: dict = {}
for _alias, _target in SYNONYMS.items():
    if isinstance(_target, str):
        _BRANDS.setdefault(_target, []).append(_alias)


def _search_terms(ingredient: str) -> List[str]:
    return [ingredient] + sorted(_BRANDS.get(ingredient, []), key=len, reverse=True)


def _external_finding(x: DrugProfile, y: DrugProfile, hit: dict) -> Optional[Finding]:
    level = hit.get("level", "Unknown")
    graded = level in SEVERITY_RANK
    sev = level if graded else MINOR
    src = f"{hit['source']}" + (f" (version {hit['version']})" if hit.get("version") else "")
    return _f(sev, "Unspecified", "external",
              f"{x.name.title()} + {y.name.title()}: interaction listed in {hit['source']}",
              "Mechanism not specified by the source database.",
              "See source record." + ("" if graded else " Severity not graded by the source."),
              "Verify in a clinical reference before acting; consult a pharmacist.",
              f"A medicine database lists an interaction between {x.name.title()} and {y.name.title()}. "
              f"Ask your pharmacist what it means for you.",
              (), (src,), "external-db", _EXT_LEVEL, x, y)


def _max_severity(findings: Sequence[Finding]) -> Optional[str]:
    if not findings:
        return None
    return max(findings, key=lambda f: SEVERITY_RANK[f.severity]).severity


def _summary_category(findings: Sequence[dict]) -> str:
    cats = set()
    for f in findings:
        if "Pharmacokinetic" in f["category"]:
            cats.add("Pharmacokinetic")
        if "Pharmacodynamic" in f["category"]:
            cats.add("Pharmacodynamic")
        if f["category"] == "Therapeutic duplication":
            cats.add("Therapeutic duplication")
        if f["category"] == "Unspecified":
            cats.add("Listed in external database")
    return " + ".join(sorted(cats)) or "Interaction"


def _worst(findings: Sequence[dict]) -> Optional[str]:
    if not findings:
        return None
    return max(findings, key=lambda f: SEVERITY_RANK[f["severity"]])["severity"]


def _profiles(resolved: Sequence[ResolvedDrug]) -> List[DrugProfile]:
    return [DRUGS[i] for r in resolved if r.recognized for i in r.ingredients]


def analyze_resolved(d1: ResolvedDrug, d2: ResolvedDrug, patient: Optional[Patient] = None,
                     _patient_ctx: Optional[dict] = None) -> dict:
    """Analyse one pair. ``_patient_ctx`` lets a regimen pass phenotypes computed over all its drugs."""
    base = {
        "drug1": d1.to_dict(),
        "drug2": d2.to_dict(),
        "kb_version": KB_VERSION,
        "disclaimer": DISCLAIMER,
    }

    if not d1.recognized or not d2.recognized:
        missing = [d.input for d in (d1, d2) if not d.recognized]
        return {**base, "status": "unrecognized_drug", "severity": UNKNOWN,
                "prediction": "Unrecognized drug", "findings": [],
                "message": "Could not identify: " + ", ".join(f"'{m}'" for m in missing) +
                           ". Check the spelling or use the generic (ingredient) name."}

    findings: List[Finding] = []
    discrepancies: List[dict] = []
    seen_titles = set()
    for i in d1.ingredients:
        for j in d2.ingredients:
            pair = _pair_findings(DRUGS[i], DRUGS[j])
            hit = evidence.external_pair(i, j) if i != j else None
            if hit:
                if not pair:
                    pair = [_external_finding(DRUGS[i], DRUGS[j], hit)]
                elif hit.get("level") in SEVERITY_RANK and \
                        SEVERITY_RANK[hit["level"]] > SEVERITY_RANK[_max_severity(pair)]:
                    discrepancies.append({"drugs": [i.title(), j.title()], "source": hit["source"],
                                          "source_severity": hit["level"], "engine_severity": _max_severity(pair)})
            citations = evidence.label_citations(i, j, {i: _search_terms(i), j: _search_terms(j)}) if i != j else []
            for f in pair:
                if f.title not in seen_titles:  # combination products can hit one rule twice
                    seen_titles.add(f.title)
                    fd = f.to_dict()
                    fd["label_evidence"] = citations
                    findings.append(fd)
    if patient is not None and not patient.empty:
        ctx = _patient_ctx or patient_alerts(_profiles([d1, d2]), patient)
        escalate(findings, patient, ctx["_phenos"])
        if _patient_ctx is None:
            base["patient_alerts"] = ctx["alerts"]
            base["phenotypes"] = ctx["phenotypes"]
    findings.sort(key=lambda f: -SEVERITY_RANK[f["severity"]])
    if discrepancies:
        base["severity_discrepancies"] = discrepancies

    if findings:
        has_curated = any(f["basis"] in {"curated", "duplication"} for f in findings)
        return {**base, "status": "interaction_found", "severity": _worst(findings),
                "prediction": _summary_category(findings),
                "confidence": "High - documented in product labeling/regulatory guidance" if has_curated
                else "Moderate - inferred from pharmacological mechanism; verify with a clinical database",
                "findings": findings,
                "message": f"{len(findings)} interaction finding(s)."}

    gaps = [d for d in (d1, d2) if not d.in_knowledge_base]
    if gaps:
        names = ", ".join(d.display_name or d.input for d in gaps)
        return {**base, "status": "insufficient_data", "severity": UNKNOWN,
                "prediction": "Insufficient data", "findings": [],
                "message": f"Recognised {names} via RxNorm, but this knowledge base has no interaction profile for "
                           f"it. Absence of an alert is NOT evidence of safety."}

    signals = [dict(sig, drugs=[i.title(), j.title()]) for i in d1.ingredients for j in d2.ingredients
               if i != j for sig in [learned.predict(i, j)] if sig]
    if signals:
        base["predicted_signals"] = signals
    return {**base, "status": "no_known_interaction", "severity": NONE_KNOWN,
            "prediction": "No known interaction", "findings": [],
            "confidence": "Limited - based on a curated knowledge base of common drugs",
            "message": "No interaction found in this knowledge base. This does not guarantee the combination is safe."}


def analyze_pair(drug1: str, drug2: str, patient: Optional[Patient] = None) -> dict:
    return analyze_resolved(resolve(drug1), resolve(drug2), patient)


def analyze_regimen(drugs: Sequence[str], patient: Optional[Patient] = None) -> dict:
    """Check every pair in a medication list (polypharmacy screen) with optional patient context."""
    patient = patient or Patient()
    resolved = [resolve(d) for d in drugs]
    profiles = _profiles(resolved)
    ctx = None if patient.empty else patient_alerts(profiles, patient)
    pairs = []
    for a, b in combinations(range(len(resolved)), 2):
        res = analyze_resolved(resolved[a], resolved[b], patient, _patient_ctx=ctx)
        pairs.append({"drug1": drugs[a], "drug2": drugs[b], "status": res["status"],
                      "severity": res["severity"], "findings": res["findings"]})
    burden = regimen_burden(profiles, age=patient.age)
    ranked = [p for p in pairs if p["severity"] in SEVERITY_RANK]
    worst = max((p["severity"] for p in ranked), key=lambda s: SEVERITY_RANK[s], default=None)
    return {
        "drugs": [r.to_dict() for r in resolved],
        "pairs": sorted(pairs, key=lambda p: -SEVERITY_RANK.get(p["severity"], 0)),
        "highest_severity": worst or (UNKNOWN if any(not r.recognized for r in resolved) else NONE_KNOWN),
        "burden": burden,
        "patient_alerts": ctx["alerts"] if ctx else [],
        "phenotypes": ctx["phenotypes"] if ctx else {},
        "kb_version": KB_VERSION,
        "disclaimer": DISCLAIMER,
    }
