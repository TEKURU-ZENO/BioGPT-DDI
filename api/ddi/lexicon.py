"""Ingredient-level drug lexicon.

Each entry describes one active ingredient:

* ``tags``     – pharmacological classes and pharmacodynamic risk flags used by
                 the rule engine (e.g. ``serotonergic``, ``qt_known``).
* ``sub``      – metabolic pathways the drug depends on:
                 ``{enzyme: "sensitive" | "moderate"}``. ``sensitive`` follows
                 the FDA definition (AUC increase >= 5-fold with a strong
                 index inhibitor); ``moderate`` means a 2- to <5-fold increase.
* ``inh``      – enzymes/transporters the drug inhibits:
                 ``{enzyme: "strong" | "moderate" | "weak"}``.
* ``ind``      – enzymes/transporters the drug induces:
                 ``{enzyme: "strong" | "moderate"}``.
* ``prodrug``  – enzyme required to convert the drug into its active form.
* ``nti``      – narrow therapeutic index (small exposure changes are harmful).

Primary source for CYP roles: U.S. FDA, "Drug Development and Drug
Interactions: Table of Substrates, Inhibitors and Inducers". Where the FDA
table is silent, classification follows the product label. The QT flag
``qt_known`` mirrors the CredibleMeds "Known Risk of TdP" category; that list
changes over time and should be re-verified at https://crediblemeds.org.

This file is a knowledge base, not a substitute for a licensed clinical
interaction database. Every change should be reviewed by a pharmacist.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, Optional

KB_VERSION = "2026.11.0"

CYP3A4 = "CYP3A4"
CYP2C9 = "CYP2C9"
CYP2C19 = "CYP2C19"
CYP2D6 = "CYP2D6"
CYP1A2 = "CYP1A2"
PGP = "P-gp"


@dataclass(frozen=True)
class DrugProfile:
    name: str
    tags: FrozenSet[str] = field(default_factory=frozenset)
    sub: Dict[str, str] = field(default_factory=dict)
    inh: Dict[str, str] = field(default_factory=dict)
    ind: Dict[str, str] = field(default_factory=dict)
    prodrug: Optional[str] = None
    nti: bool = False

    def has(self, tag: str) -> bool:
        return tag in self.tags


def _d(*tags, sub=None, inh=None, ind=None, prodrug=None, nti=False):
    return dict(tags=frozenset(tags), sub=sub or {}, inh=inh or {}, ind=ind or {},
                prodrug=prodrug, nti=nti)


S, M = "sensitive", "moderate"
STRONG, MOD, WEAK = "strong", "moderate", "weak"

_RAW: Dict[str, dict] = {
    # ---------------------------------------------------------------- anticoagulants
    "warfarin": _d("anticoagulant", "vitamin_k_antagonist", sub={CYP2C9: S}, nti=True),
    "apixaban": _d("anticoagulant", "doac", sub={CYP3A4: M, PGP: M}),
    "rivaroxaban": _d("anticoagulant", "doac", sub={CYP3A4: M, PGP: M}),
    "dabigatran": _d("anticoagulant", "doac", sub={PGP: S}),
    "edoxaban": _d("anticoagulant", "doac", sub={PGP: M}),
    "heparin": _d("anticoagulant"),
    "enoxaparin": _d("anticoagulant"),
    # ---------------------------------------------------------------- antiplatelets
    "aspirin": _d("antiplatelet", "salicylate"),
    "clopidogrel": _d("antiplatelet", "p2y12_inhibitor", prodrug=CYP2C19),
    "prasugrel": _d("antiplatelet", "p2y12_inhibitor"),
    "ticagrelor": _d("antiplatelet", "p2y12_inhibitor", sub={CYP3A4: M}),
    "dipyridamole": _d("antiplatelet"),
    "cilostazol": _d("antiplatelet", sub={CYP3A4: M}),
    # ---------------------------------------------------------------- NSAIDs
    "ibuprofen": _d("nsaid"),
    "naproxen": _d("nsaid"),
    "diclofenac": _d("nsaid"),
    "celecoxib": _d("nsaid", sub={CYP2C9: S}),
    "indomethacin": _d("nsaid"),
    "meloxicam": _d("nsaid"),
    "ketorolac": _d("nsaid"),
    "piroxicam": _d("nsaid"),
    "ketoprofen": _d("nsaid"),
    # ---------------------------------------------------------------- antidepressants
    "fluoxetine": _d("ssri", "serotonergic", "bleeding_serotonergic", inh={CYP2D6: STRONG, CYP2C19: MOD}),
    "sertraline": _d("ssri", "serotonergic", "bleeding_serotonergic"),
    "paroxetine": _d("ssri", "serotonergic", "bleeding_serotonergic", inh={CYP2D6: STRONG}),
    "citalopram": _d("ssri", "serotonergic", "bleeding_serotonergic", "qt_known", sub={CYP2C19: M}),
    "escitalopram": _d("ssri", "serotonergic", "bleeding_serotonergic", "qt_known"),
    "fluvoxamine": _d("ssri", "serotonergic", "bleeding_serotonergic", inh={CYP1A2: STRONG, CYP2C19: STRONG}),
    "venlafaxine": _d("snri", "serotonergic", "bleeding_serotonergic", sub={CYP2D6: S}),
    "desvenlafaxine": _d("snri", "serotonergic", "bleeding_serotonergic"),
    "duloxetine": _d("snri", "serotonergic", "bleeding_serotonergic", sub={CYP1A2: S}, inh={CYP2D6: MOD}),
    "amitriptyline": _d("tca", "serotonergic", "cns_depressant", "seizure_threshold", sub={CYP2D6: M}),
    "nortriptyline": _d("tca", "serotonergic", "seizure_threshold", sub={CYP2D6: S}),
    "clomipramine": _d("tca", "serotonergic", "bleeding_serotonergic", "seizure_threshold"),
    "trazodone": _d("serotonergic", "cns_depressant", sub={CYP3A4: M}),
    "mirtazapine": _d("serotonergic", "cns_depressant"),
    "bupropion": _d("aminoketone", "seizure_threshold", inh={CYP2D6: STRONG}),
    "buspirone": _d("serotonergic", sub={CYP3A4: S}),
    "lithium": _d("lithium", "serotonergic", nti=True),
    "st john's wort": _d("serotonergic", "herbal", ind={CYP3A4: STRONG, PGP: STRONG}),
    # ---------------------------------------------------------------- MAO inhibitors
    "phenelzine": _d("maoi", "serotonergic"),
    "tranylcypromine": _d("maoi", "serotonergic"),
    "isocarboxazid": _d("maoi", "serotonergic"),
    "selegiline": _d("maoi", "serotonergic"),
    "rasagiline": _d("maoi", "serotonergic"),
    "linezolid": _d("maoi", "serotonergic", "antibiotic"),
    "methylene blue": _d("maoi", "serotonergic"),
    # ---------------------------------------------------------------- triptans
    "sumatriptan": _d("triptan", "serotonergic"),
    "rizatriptan": _d("triptan", "serotonergic"),
    "zolmitriptan": _d("triptan", "serotonergic"),
    # ---------------------------------------------------------------- opioids
    "morphine": _d("opioid", "cns_depressant"),
    "hydromorphone": _d("opioid", "cns_depressant"),
    "oxycodone": _d("opioid", "cns_depressant", sub={CYP3A4: M}),
    "hydrocodone": _d("opioid", "cns_depressant", sub={CYP3A4: M}),
    "fentanyl": _d("opioid", "cns_depressant", "serotonergic", sub={CYP3A4: S}),
    "codeine": _d("opioid", "cns_depressant", prodrug=CYP2D6),
    "tramadol": _d("opioid", "cns_depressant", "serotonergic", "seizure_threshold", sub={CYP3A4: M}, prodrug=CYP2D6),
    "tapentadol": _d("opioid", "cns_depressant", "serotonergic"),
    "methadone": _d("opioid", "cns_depressant", "serotonergic", "qt_known", sub={CYP3A4: M}),
    "buprenorphine": _d("opioid", "cns_depressant", sub={CYP3A4: M}),
    "meperidine": _d("opioid", "cns_depressant", "serotonergic", "seizure_threshold"),
    "dextromethorphan": _d("serotonergic", "antitussive", sub={CYP2D6: S}),
    # ---------------------------------------------------------------- sedatives / hypnotics
    "diazepam": _d("benzodiazepine", "cns_depressant", sub={CYP2C19: M, CYP3A4: M}),
    "alprazolam": _d("benzodiazepine", "cns_depressant", sub={CYP3A4: M}),
    "lorazepam": _d("benzodiazepine", "cns_depressant"),
    "clonazepam": _d("benzodiazepine", "cns_depressant", sub={CYP3A4: M}),
    "midazolam": _d("benzodiazepine", "cns_depressant", sub={CYP3A4: S}),
    "triazolam": _d("benzodiazepine", "cns_depressant", sub={CYP3A4: S}),
    "temazepam": _d("benzodiazepine", "cns_depressant"),
    "zolpidem": _d("z_drug", "cns_depressant", sub={CYP3A4: M}),
    "eszopiclone": _d("z_drug", "cns_depressant", sub={CYP3A4: M}),
    "zopiclone": _d("z_drug", "cns_depressant", sub={CYP3A4: M}),
    "gabapentin": _d("gabapentinoid", "cns_depressant"),
    "pregabalin": _d("gabapentinoid", "cns_depressant"),
    "phenobarbital": _d("barbiturate", "cns_depressant", "antiepileptic", ind={CYP3A4: MOD}),
    "alcohol": _d("alcohol", "cns_depressant"),
    "quetiapine": _d("antipsychotic", "cns_depressant", sub={CYP3A4: S}),
    "olanzapine": _d("antipsychotic", "cns_depressant", sub={CYP1A2: M}),
    "clozapine": _d("antipsychotic", "cns_depressant", "seizure_threshold", sub={CYP1A2: M}, nti=True),
    "haloperidol": _d("antipsychotic", "qt_known"),
    "chlorpromazine": _d("antipsychotic", "qt_known", "cns_depressant", "seizure_threshold"),
    "cyclobenzaprine": _d("muscle_relaxant", "cns_depressant", "serotonergic"),
    "carisoprodol": _d("muscle_relaxant", "cns_depressant"),
    "tizanidine": _d("muscle_relaxant", "cns_depressant", sub={CYP1A2: S}),
    "diphenhydramine": _d("antihistamine_sedating", "cns_depressant"),
    "hydroxyzine": _d("antihistamine_sedating", "cns_depressant"),
    # ---------------------------------------------------------------- lipid lowering
    "simvastatin": _d("statin", sub={CYP3A4: S}),
    "lovastatin": _d("statin", sub={CYP3A4: S}),
    "atorvastatin": _d("statin", sub={CYP3A4: M}),
    "rosuvastatin": _d("statin"),
    "pravastatin": _d("statin"),
    "pitavastatin": _d("statin"),
    "fluvastatin": _d("statin", sub={CYP2C9: M}),
    "gemfibrozil": _d("fibrate"),
    "fenofibrate": _d("fibrate"),
    # ---------------------------------------------------------------- anti-infectives
    "clarithromycin": _d("macrolide", "antibiotic", "qt_known", inh={CYP3A4: STRONG, PGP: MOD}),
    "erythromycin": _d("macrolide", "antibiotic", "qt_known", inh={CYP3A4: MOD, PGP: MOD}),
    "azithromycin": _d("macrolide", "antibiotic", "qt_known"),
    "ketoconazole": _d("azole", "antifungal", inh={CYP3A4: STRONG, PGP: MOD}),
    "itraconazole": _d("azole", "antifungal", inh={CYP3A4: STRONG, PGP: MOD}),
    "posaconazole": _d("azole", "antifungal", inh={CYP3A4: STRONG}),
    "voriconazole": _d("azole", "antifungal", inh={CYP3A4: STRONG, CYP2C19: MOD}),
    "fluconazole": _d("azole", "antifungal", "qt_known", inh={CYP3A4: MOD, CYP2C9: MOD, CYP2C19: STRONG}),
    "miconazole": _d("azole", "antifungal"),
    "ritonavir": _d("antiretroviral", "pk_booster", inh={CYP3A4: STRONG, PGP: MOD}),
    "cobicistat": _d("antiretroviral", "pk_booster", inh={CYP3A4: STRONG, PGP: MOD}),
    "efavirenz": _d("antiretroviral", ind={CYP3A4: MOD}),
    "ciprofloxacin": _d("fluoroquinolone", "antibiotic", "qt_known", inh={CYP1A2: STRONG, CYP3A4: MOD}),
    "levofloxacin": _d("fluoroquinolone", "antibiotic", "qt_known"),
    "moxifloxacin": _d("fluoroquinolone", "antibiotic", "qt_known"),
    "doxycycline": _d("tetracycline", "antibiotic"),
    "tetracycline": _d("tetracycline", "antibiotic"),
    "minocycline": _d("tetracycline", "antibiotic"),
    "metronidazole": _d("nitroimidazole", "antibiotic", "disulfiram_like"),
    "tinidazole": _d("nitroimidazole", "antibiotic", "disulfiram_like"),
    "disulfiram": _d("disulfiram_like"),
    "sulfamethoxazole": _d("sulfonamide", "antibiotic"),
    "trimethoprim": _d("antibiotic", "antifolate_weak", "k_retaining"),
    "amoxicillin": _d("penicillin", "antibiotic"),
    "penicillin": _d("penicillin", "antibiotic"),
    "rifampin": _d("rifamycin", "antibiotic",
                   ind={CYP3A4: STRONG, CYP2C19: STRONG, CYP2C9: MOD, CYP1A2: MOD, PGP: STRONG}),
    "rifabutin": _d("rifamycin", "antibiotic", ind={CYP3A4: MOD}),
    "hydroxychloroquine": _d("antimalarial", "qt_known"),
    # ---------------------------------------------------------------- cardiovascular
    "amiodarone": _d("antiarrhythmic", "qt_known", inh={CYP2C9: MOD, PGP: MOD, CYP3A4: WEAK}),
    "dronedarone": _d("antiarrhythmic", "qt_known", inh={CYP3A4: MOD, PGP: MOD}, sub={CYP3A4: S}),
    "sotalol": _d("antiarrhythmic", "beta_blocker", "bradycardic", "qt_known"),
    "dofetilide": _d("antiarrhythmic", "qt_known", nti=True),
    "quinidine": _d("antiarrhythmic", "qt_known", inh={CYP2D6: STRONG, PGP: MOD}),
    "flecainide": _d("antiarrhythmic", "qt_known", sub={CYP2D6: M}, nti=True),
    "digoxin": _d("cardiac_glycoside", "bradycardic", sub={PGP: S}, nti=True),
    "verapamil": _d("nondhp_ccb", "bradycardic", inh={CYP3A4: MOD, PGP: MOD}),
    "diltiazem": _d("nondhp_ccb", "bradycardic", inh={CYP3A4: MOD}),
    "amlodipine": _d("dhp_ccb", "antihypertensive", sub={CYP3A4: M}, inh={CYP3A4: WEAK}),
    "nifedipine": _d("dhp_ccb", "antihypertensive", sub={CYP3A4: S}),
    "metoprolol": _d("beta_blocker", "bradycardic", sub={CYP2D6: M}),
    "atenolol": _d("beta_blocker", "bradycardic"),
    "propranolol": _d("beta_blocker", "bradycardic", sub={CYP2D6: M}),
    "carvedilol": _d("beta_blocker", "bradycardic"),
    "bisoprolol": _d("beta_blocker", "bradycardic"),
    "nebivolol": _d("beta_blocker", "bradycardic", sub={CYP2D6: S}),
    "nitroglycerin": _d("nitrate"),
    "isosorbide mononitrate": _d("nitrate"),
    "isosorbide dinitrate": _d("nitrate"),
    "sildenafil": _d("pde5_inhibitor", sub={CYP3A4: S}),
    "tadalafil": _d("pde5_inhibitor", sub={CYP3A4: M}),
    "vardenafil": _d("pde5_inhibitor", sub={CYP3A4: S}),
    "riociguat": _d("sgc_stimulator"),
    "tamsulosin": _d("alpha_blocker"),
    "doxazosin": _d("alpha_blocker"),
    "terazosin": _d("alpha_blocker"),
    "prazosin": _d("alpha_blocker"),
    "lisinopril": _d("acei", "raas"),
    "enalapril": _d("acei", "raas"),
    "ramipril": _d("acei", "raas"),
    "perindopril": _d("acei", "raas"),
    "captopril": _d("acei", "raas"),
    "benazepril": _d("acei", "raas"),
    "losartan": _d("arb", "raas"),
    "valsartan": _d("arb", "raas"),
    "irbesartan": _d("arb", "raas"),
    "candesartan": _d("arb", "raas"),
    "olmesartan": _d("arb", "raas"),
    "telmisartan": _d("arb", "raas"),
    "sacubitril": _d("neprilysin_inhibitor"),
    "aliskiren": _d("renin_inhibitor", "raas"),
    "spironolactone": _d("k_sparing", "k_retaining", "diuretic"),
    "eplerenone": _d("k_sparing", "k_retaining", "diuretic", sub={CYP3A4: S}),
    "amiloride": _d("k_sparing", "k_retaining", "diuretic"),
    "triamterene": _d("k_sparing", "k_retaining", "diuretic"),
    "potassium chloride": _d("potassium"),
    "hydrochlorothiazide": _d("thiazide", "diuretic"),
    "chlorthalidone": _d("thiazide", "diuretic"),
    "indapamide": _d("thiazide", "diuretic"),
    "furosemide": _d("loop_diuretic", "diuretic"),
    "bumetanide": _d("loop_diuretic", "diuretic"),
    "torsemide": _d("loop_diuretic", "diuretic"),
    # ---------------------------------------------------------------- endocrine / metabolic
    "metformin": _d("biguanide", "antidiabetic"),
    "insulin": _d("insulin", "hypoglycemic", "antidiabetic"),
    "glipizide": _d("sulfonylurea", "hypoglycemic", "antidiabetic", sub={CYP2C9: M}),
    "glyburide": _d("sulfonylurea", "hypoglycemic", "antidiabetic", sub={CYP2C9: M}),
    "glimepiride": _d("sulfonylurea", "hypoglycemic", "antidiabetic", sub={CYP2C9: M}),
    "repaglinide": _d("meglitinide", "hypoglycemic", "antidiabetic"),
    "sitagliptin": _d("dpp4_inhibitor", "antidiabetic"),
    "empagliflozin": _d("sglt2_inhibitor", "antidiabetic"),
    "dapagliflozin": _d("sglt2_inhibitor", "antidiabetic"),
    "pioglitazone": _d("thiazolidinedione", "antidiabetic"),
    "levothyroxine": _d("thyroid_hormone", "chelation_sensitive"),
    "ethinyl estradiol": _d("hormonal_contraceptive", sub={CYP3A4: M}),
    "calcium carbonate": _d("polyvalent_cation", "antacid"),
    "ferrous sulfate": _d("polyvalent_cation", "iron"),
    "magnesium hydroxide": _d("polyvalent_cation", "antacid"),
    "aluminum hydroxide": _d("polyvalent_cation", "antacid"),
    "omeprazole": _d("ppi", sub={CYP2C19: S}, inh={CYP2C19: MOD}),
    "esomeprazole": _d("ppi", sub={CYP2C19: M}, inh={CYP2C19: MOD}),
    "pantoprazole": _d("ppi"),
    "lansoprazole": _d("ppi"),
    "rabeprazole": _d("ppi"),
    "famotidine": _d("h2_blocker"),
    "acetaminophen": _d("analgesic"),
    "phytonadione": _d("vitamin_k"),
    "pseudoephedrine": _d("sympathomimetic"),
    "ascorbic acid": _d("vitamin"),
    "cholecalciferol": _d("vitamin"),
    "cyanocobalamin": _d("vitamin"),
    "folic acid": _d("vitamin"),
    "omega-3 fatty acids": _d("supplement"),
    "grapefruit juice": _d("food", inh={CYP3A4: MOD}),
    # ---------------------------------------------------------------- immunology / oncology
    "tacrolimus": _d("calcineurin_inhibitor", "immunosuppressant", "k_retaining", sub={CYP3A4: S}, nti=True),
    "cyclosporine": _d("calcineurin_inhibitor", "immunosuppressant", "k_retaining", sub={CYP3A4: M},
                       inh={CYP3A4: MOD, PGP: MOD}, nti=True),
    "sirolimus": _d("mtor_inhibitor", "immunosuppressant", sub={CYP3A4: S}, nti=True),
    "everolimus": _d("mtor_inhibitor", "immunosuppressant", sub={CYP3A4: S}),
    "azathioprine": _d("thiopurine", "immunosuppressant"),
    "mercaptopurine": _d("thiopurine", "immunosuppressant"),
    "methotrexate": _d("antifolate", "immunosuppressant", nti=True),
    "allopurinol": _d("xanthine_oxidase_inhibitor"),
    "febuxostat": _d("xanthine_oxidase_inhibitor"),
    "colchicine": _d("antigout", sub={CYP3A4: M, PGP: S}, nti=True),
    "tamoxifen": _d("serm", prodrug=CYP2D6),
    # co-ingredients of combination products (no interaction-relevant flags yet)
    "ezetimibe": _d("cholesterol_absorption_inhibitor"),
    "clavulanate": _d("beta_lactamase_inhibitor"),
    "nirmatrelvir": _d("antiviral", sub={CYP3A4: M}),
    # ---------------------------------------------------------------- neurology / other
    "carbamazepine": _d("antiepileptic", sub={CYP3A4: M}, ind={CYP3A4: STRONG, PGP: MOD}, nti=True),
    "phenytoin": _d("antiepileptic", sub={CYP2C9: M}, ind={CYP3A4: STRONG, PGP: MOD}, nti=True),
    "valproate": _d("antiepileptic"),
    "lamotrigine": _d("antiepileptic"),
    "levetiracetam": _d("antiepileptic", "cns_depressant"),
    "topiramate": _d("antiepileptic"),
    "theophylline": _d("methylxanthine", "seizure_threshold", sub={CYP1A2: M}, nti=True),
    "donepezil": _d("cholinesterase_inhibitor", "qt_known"),
    "ondansetron": _d("antiemetic", "qt_known", "serotonergic"),
    "domperidone": _d("antiemetic", "qt_known", sub={CYP3A4: S}),
}

DRUGS: Dict[str, DrugProfile] = {name: DrugProfile(name=name, **spec) for name, spec in _RAW.items()}

_SUB_LEVELS, _MOD_LEVELS = {"sensitive", "moderate"}, {"strong", "moderate", "weak"}


def merge_roles(drugs: Dict[str, DrugProfile], data: dict, synonyms: Optional[Dict[str, object]] = None) -> dict:
    """Merge generated CYP/P-gp roles (scripts/import_fda_cyp_table.py) into ``drugs`` in place.

    Hand-curated roles always win; disagreements are returned as ``conflicts``
    for pharmacist review. Unknown drugs become mechanism-only profiles.
    """
    synonyms = SYNONYMS if synonyms is None else synonyms
    added, enriched, conflicts = [], [], []
    for raw_name, roles in (data.get("roles") or {}).items():
        target = synonyms.get(raw_name, raw_name)
        if isinstance(target, list):
            continue
        sub = {e: v for e, v in (roles.get("sub") or {}).items() if v in _SUB_LEVELS}
        inh = {e: v for e, v in (roles.get("inh") or {}).items() if v in _MOD_LEVELS}
        ind = {e: v for e, v in (roles.get("ind") or {}).items() if v in ("strong", "moderate")}
        if target in drugs:
            prof, changed = drugs[target], False
            for mine, theirs, label in ((prof.sub, sub, "substrate"), (prof.inh, inh, "inhibitor"),
                                        (prof.ind, ind, "inducer")):
                for enz, level in theirs.items():
                    if enz not in mine:
                        mine[enz] = level
                        changed = True
                    elif mine[enz] != level:
                        conflicts.append({"drug": target, "role": label, "enzyme": enz,
                                          "lexicon": mine[enz], "fda_table": level})
            if changed:
                enriched.append(target)
        elif sub or inh or ind:
            drugs[target] = DrugProfile(name=target, tags=frozenset({"fda_cyp_table"}), sub=sub, inh=inh, ind=ind)
            added.append(target)
    return {"added": sorted(added), "enriched": sorted(enriched), "conflicts": conflicts}


def _generated_roles_path() -> Path:
    base = os.getenv("DDI_DATA_DIR") or str(Path(__file__).resolve().parent / "data")
    return Path(base) / "fda_cyp_roles.json"


GENERATED_ROLES: dict = {"loaded": False}


# Brand names, abbreviations, international names and common lay terms.
# A value that is a list denotes a fixed-dose combination product.
SYNONYMS: Dict[str, object] = {
    # anticoagulants / antiplatelets
    "coumadin": "warfarin", "jantoven": "warfarin", "eliquis": "apixaban", "xarelto": "rivaroxaban",
    "pradaxa": "dabigatran", "savaysa": "edoxaban", "lixiana": "edoxaban", "lovenox": "enoxaparin",
    "clexane": "enoxaparin", "plavix": "clopidogrel", "effient": "prasugrel", "brilinta": "ticagrelor",
    "persantine": "dipyridamole", "pletal": "cilostazol",
    "asa": "aspirin", "acetylsalicylic acid": "aspirin", "ecotrin": "aspirin", "bayer aspirin": "aspirin",
    "aggrenox": ["aspirin", "dipyridamole"],
    # analgesics / NSAIDs
    "advil": "ibuprofen", "motrin": "ibuprofen", "nurofen": "ibuprofen", "aleve": "naproxen",
    "naprosyn": "naproxen", "voltaren": "diclofenac", "celebrex": "celecoxib", "indocin": "indomethacin",
    "mobic": "meloxicam", "toradol": "ketorolac", "feldene": "piroxicam",
    "tylenol": "acetaminophen", "paracetamol": "acetaminophen", "apap": "acetaminophen",
    "panadol": "acetaminophen", "calpol": "acetaminophen",
    "percocet": ["oxycodone", "acetaminophen"], "vicodin": ["hydrocodone", "acetaminophen"],
    "norco": ["hydrocodone", "acetaminophen"], "tylenol with codeine": ["codeine", "acetaminophen"],
    "oxycontin": "oxycodone", "roxicodone": "oxycodone", "duragesic": "fentanyl", "sublimaze": "fentanyl",
    "ultram": "tramadol", "nucynta": "tapentadol", "dolophine": "methadone", "subutex": "buprenorphine",
    "suboxone": "buprenorphine", "dilaudid": "hydromorphone", "demerol": "meperidine", "pethidine": "meperidine",
    "ms contin": "morphine", "robitussin dm": "dextromethorphan", "dxm": "dextromethorphan",
    # psychiatric
    "prozac": "fluoxetine", "sarafem": "fluoxetine", "zoloft": "sertraline", "lustral": "sertraline",
    "paxil": "paroxetine", "seroxat": "paroxetine", "celexa": "citalopram", "cipramil": "citalopram",
    "lexapro": "escitalopram", "cipralex": "escitalopram", "luvox": "fluvoxamine", "effexor": "venlafaxine",
    "pristiq": "desvenlafaxine", "cymbalta": "duloxetine", "elavil": "amitriptyline", "pamelor": "nortriptyline",
    "anafranil": "clomipramine", "desyrel": "trazodone", "remeron": "mirtazapine", "wellbutrin": "bupropion",
    "zyban": "bupropion", "buspar": "buspirone", "lithobid": "lithium", "lithium carbonate": "lithium",
    "st johns wort": "st john's wort", "st. john's wort": "st john's wort", "saint john's wort": "st john's wort",
    "hypericum": "st john's wort", "hypericum perforatum": "st john's wort",
    "nardil": "phenelzine", "parnate": "tranylcypromine", "marplan": "isocarboxazid", "emsam": "selegiline",
    "eldepryl": "selegiline", "zelapar": "selegiline", "azilect": "rasagiline", "zyvox": "linezolid",
    "provayblue": "methylene blue", "methylthioninium chloride": "methylene blue",
    "imitrex": "sumatriptan", "maxalt": "rizatriptan", "zomig": "zolmitriptan",
    "valium": "diazepam", "xanax": "alprazolam", "ativan": "lorazepam", "klonopin": "clonazepam",
    "rivotril": "clonazepam", "versed": "midazolam", "halcion": "triazolam", "restoril": "temazepam",
    "ambien": "zolpidem", "stilnox": "zolpidem", "lunesta": "eszopiclone", "imovane": "zopiclone",
    "neurontin": "gabapentin", "lyrica": "pregabalin", "luminal": "phenobarbital",
    "ethanol": "alcohol", "ethyl alcohol": "alcohol", "beer": "alcohol", "wine": "alcohol", "liquor": "alcohol",
    "seroquel": "quetiapine", "zyprexa": "olanzapine", "clozaril": "clozapine", "haldol": "haloperidol",
    "thorazine": "chlorpromazine", "flexeril": "cyclobenzaprine", "soma": "carisoprodol", "zanaflex": "tizanidine",
    "benadryl": "diphenhydramine", "atarax": "hydroxyzine", "vistaril": "hydroxyzine",
    # lipids
    "zocor": "simvastatin", "mevacor": "lovastatin", "lipitor": "atorvastatin", "crestor": "rosuvastatin",
    "pravachol": "pravastatin", "livalo": "pitavastatin", "lescol": "fluvastatin", "lopid": "gemfibrozil",
    "tricor": "fenofibrate", "vytorin": ["simvastatin", "ezetimibe"], "caduet": ["amlodipine", "atorvastatin"],
    # anti-infectives
    "biaxin": "clarithromycin", "klacid": "clarithromycin", "ery-tab": "erythromycin", "eryc": "erythromycin",
    "zithromax": "azithromycin", "z-pak": "azithromycin", "zpack": "azithromycin", "nizoral": "ketoconazole",
    "sporanox": "itraconazole", "noxafil": "posaconazole", "vfend": "voriconazole", "diflucan": "fluconazole",
    "monistat": "miconazole", "daktarin": "miconazole", "norvir": "ritonavir", "tybost": "cobicistat",
    "paxlovid": ["nirmatrelvir", "ritonavir"], "sustiva": "efavirenz",
    "cipro": "ciprofloxacin", "levaquin": "levofloxacin", "avelox": "moxifloxacin", "vibramycin": "doxycycline",
    "minocin": "minocycline", "flagyl": "metronidazole", "tindamax": "tinidazole", "antabuse": "disulfiram",
    "bactrim": ["sulfamethoxazole", "trimethoprim"], "septra": ["sulfamethoxazole", "trimethoprim"],
    "co-trimoxazole": ["sulfamethoxazole", "trimethoprim"], "cotrimoxazole": ["sulfamethoxazole", "trimethoprim"],
    "tmp-smx": ["sulfamethoxazole", "trimethoprim"], "smx-tmp": ["sulfamethoxazole", "trimethoprim"],
    "amoxil": "amoxicillin", "augmentin": ["amoxicillin", "clavulanate"], "penicillin v": "penicillin",
    "rifampicin": "rifampin", "rifadin": "rifampin", "mycobutin": "rifabutin", "plaquenil": "hydroxychloroquine",
    # cardiovascular
    "cordarone": "amiodarone", "pacerone": "amiodarone", "multaq": "dronedarone", "betapace": "sotalol",
    "tikosyn": "dofetilide", "tambocor": "flecainide", "lanoxin": "digoxin", "calan": "verapamil",
    "isoptin": "verapamil", "cardizem": "diltiazem", "norvasc": "amlodipine", "procardia": "nifedipine",
    "adalat": "nifedipine", "lopressor": "metoprolol", "toprol": "metoprolol", "toprol xl": "metoprolol",
    "tenormin": "atenolol", "inderal": "propranolol", "coreg": "carvedilol", "zebeta": "bisoprolol",
    "bystolic": "nebivolol", "nitrostat": "nitroglycerin", "glyceryl trinitrate": "nitroglycerin",
    "gtn": "nitroglycerin", "imdur": "isosorbide mononitrate", "isordil": "isosorbide dinitrate",
    "viagra": "sildenafil", "revatio": "sildenafil", "cialis": "tadalafil", "adcirca": "tadalafil",
    "levitra": "vardenafil", "adempas": "riociguat", "flomax": "tamsulosin", "cardura": "doxazosin",
    "hytrin": "terazosin", "minipress": "prazosin",
    "zestril": "lisinopril", "prinivil": "lisinopril", "vasotec": "enalapril", "altace": "ramipril",
    "coversyl": "perindopril", "capoten": "captopril", "lotensin": "benazepril", "cozaar": "losartan",
    "diovan": "valsartan", "avapro": "irbesartan", "atacand": "candesartan", "benicar": "olmesartan",
    "micardis": "telmisartan", "entresto": ["sacubitril", "valsartan"], "tekturna": "aliskiren",
    "aldactone": "spironolactone", "inspra": "eplerenone", "midamor": "amiloride", "dyrenium": "triamterene",
    "dyazide": ["triamterene", "hydrochlorothiazide"], "maxzide": ["triamterene", "hydrochlorothiazide"],
    "zestoretic": ["lisinopril", "hydrochlorothiazide"], "hyzaar": ["losartan", "hydrochlorothiazide"],
    "potassium": "potassium chloride", "kcl": "potassium chloride", "klor-con": "potassium chloride",
    "slow-k": "potassium chloride", "potassium supplement": "potassium chloride",
    "hctz": "hydrochlorothiazide", "microzide": "hydrochlorothiazide", "hygroton": "chlorthalidone",
    "lasix": "furosemide", "frusemide": "furosemide", "bumex": "bumetanide", "demadex": "torsemide",
    # endocrine / GI / misc
    "glucophage": "metformin", "glucotrol": "glipizide", "diabeta": "glyburide", "glibenclamide": "glyburide",
    "micronase": "glyburide", "amaryl": "glimepiride", "prandin": "repaglinide", "januvia": "sitagliptin",
    "janumet": ["sitagliptin", "metformin"], "jardiance": "empagliflozin", "farxiga": "dapagliflozin",
    "actos": "pioglitazone", "humalog": "insulin", "novolog": "insulin", "lantus": "insulin",
    "insulin glargine": "insulin", "insulin lispro": "insulin", "insulin aspart": "insulin",
    "synthroid": "levothyroxine", "levoxyl": "levothyroxine", "eltroxin": "levothyroxine",
    "thyroxine": "levothyroxine", "l-thyroxine": "levothyroxine",
    "birth control pill": "ethinyl estradiol", "oral contraceptive": "ethinyl estradiol",
    "combined oral contraceptive": "ethinyl estradiol", "the pill": "ethinyl estradiol",
    "tums": "calcium carbonate", "calcium": "calcium carbonate", "iron": "ferrous sulfate",
    "iron supplement": "ferrous sulfate", "feso4": "ferrous sulfate", "milk of magnesia": "magnesium hydroxide",
    "magnesium": "magnesium hydroxide", "maalox": ["aluminum hydroxide", "magnesium hydroxide"],
    "mylanta": ["aluminum hydroxide", "magnesium hydroxide"], "antacid": ["aluminum hydroxide", "magnesium hydroxide"],
    "prilosec": "omeprazole", "losec": "omeprazole", "nexium": "esomeprazole", "protonix": "pantoprazole",
    "prevacid": "lansoprazole", "aciphex": "rabeprazole", "pepcid": "famotidine",
    "vitamin k": "phytonadione", "vitamin k1": "phytonadione", "mephyton": "phytonadione",
    "sudafed": "pseudoephedrine", "vitamin c": "ascorbic acid", "vitamin d": "cholecalciferol",
    "vitamin d3": "cholecalciferol", "vitamin b12": "cyanocobalamin", "folate": "folic acid",
    "fish oil": "omega-3 fatty acids", "omega 3": "omega-3 fatty acids", "grapefruit": "grapefruit juice",
    "prograf": "tacrolimus", "advagraf": "tacrolimus", "envarsus": "tacrolimus", "neoral": "cyclosporine",
    "sandimmune": "cyclosporine", "gengraf": "cyclosporine", "ciclosporin": "cyclosporine",
    "rapamune": "sirolimus", "afinitor": "everolimus", "zortress": "everolimus", "imuran": "azathioprine",
    "purinethol": "mercaptopurine", "6-mp": "mercaptopurine", "trexall": "methotrexate",
    "otrexup": "methotrexate", "rasuvo": "methotrexate", "zyloprim": "allopurinol", "uloric": "febuxostat",
    "colcrys": "colchicine", "mitigare": "colchicine", "nolvadex": "tamoxifen",
    "tegretol": "carbamazepine", "carbatrol": "carbamazepine", "dilantin": "phenytoin",
    "depakote": "valproate", "depakene": "valproate", "valproic acid": "valproate",
    "divalproex": "valproate", "sodium valproate": "valproate", "lamictal": "lamotrigine",
    "keppra": "levetiracetam", "topamax": "topiramate", "theo-24": "theophylline", "uniphyl": "theophylline",
    "aminophylline": "theophylline", "aricept": "donepezil", "zofran": "ondansetron", "motilium": "domperidone",
}

# Salt / formulation words that do not change the active moiety.
SALT_WORDS = {
    "hydrochloride", "hcl", "hyclate", "monohydrate", "sodium", "potassium", "calcium", "magnesium",
    "maleate", "mesylate", "besylate", "succinate", "tartrate", "citrate", "sulfate", "sulphate",
    "phosphate", "bromide", "acetate", "fumarate", "dihydrate", "trihydrate", "er", "xr", "sr", "cr",
    "xl", "la", "dr", "ec", "odt", "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap",
    "oral", "injection", "solution", "suspension", "extended", "release", "delayed", "film", "coated",
    "hr", "hour", "day", "chewable", "sublingual", "transdermal", "patch", "topical", "cream", "gel",
    "injectable", "prefilled", "syringe", "pen", "vial", "inhaler", "metered", "dose", "actuat", "ml",
    "disintegrating", "enteric", "product", "kit", "system",
}


def _load_generated_roles() -> None:
    path = _generated_roles_path()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    stats = merge_roles(DRUGS, data)
    GENERATED_ROLES.update({"loaded": True, "source": data.get("source"), "retrieved": data.get("retrieved"),
                            "added": len(stats["added"]), "enriched": len(stats["enriched"]),
                            "conflicts": stats["conflicts"]})


_load_generated_roles()
