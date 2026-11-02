"""Curated, source-attributed interaction rules.

Curated rules take precedence over the mechanism engine. A rule lists the
mechanism ``covers`` axes it explains (e.g. ``"pk"`` for any pharmacokinetic
axis, ``"bleeding"``); engine findings on a covered axis are suppressed for
that pair so the same interaction is not reported twice.

Selectors: a plain string matches an ingredient name; ``"@tag"`` matches any
ingredient carrying that tag in :mod:`api.ddi.lexicon`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

CONTRAINDICATED, MAJOR, MODERATE, MINOR = "Contraindicated", "Major", "Moderate", "Minor"

PK, PD = "Pharmacokinetic", "Pharmacodynamic"

# Frequently cited sources
SRC_FDA_CYP = "FDA: Drug Development and Drug Interactions - Table of Substrates, Inhibitors and Inducers"
SRC_WARFARIN_PI = "Warfarin (Coumadin) US Prescribing Information, Section 7: Drug Interactions"
SRC_SIMVA_DSC = "FDA Drug Safety Communication (June 2011): new restrictions and dose limitations for simvastatin"
SRC_CLOPI_DSC = "FDA Drug Safety Communication (Nov 2009, Oct 2010): avoid clopidogrel with omeprazole/esomeprazole"
SRC_OPI_BZD_DSC = "FDA Drug Safety Communication (Aug 2016): boxed warning for opioids combined with benzodiazepines"
SRC_GABA_DSC = "FDA Drug Safety Communication (Dec 2019): respiratory depression with gabapentinoids and CNS depressants"
SRC_LINEZOLID_DSC = "FDA Drug Safety Communication (2011): serotonin syndrome with linezolid / methylene blue and serotonergic drugs"
SRC_SEROTONIN = "Boyer EW, Shannon M. The serotonin syndrome. N Engl J Med 2005;352:1112-20"
SRC_CREDIBLEMEDS = "CredibleMeds QTdrugs list, 'Known Risk of TdP' category (verify current status at crediblemeds.org)"


@dataclass(frozen=True)
class Rule:
    a: Tuple[str, ...]
    b: Tuple[str, ...]
    severity: str
    category: str
    title: str
    mechanism: str
    effect: str
    management: str
    patient: str
    watch: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()
    covers: Tuple[str, ...] = ()


def R(a, b, severity, category, title, mechanism, effect, management, patient,
      watch=(), evidence=(), covers=()):
    as_t = lambda x: (x,) if isinstance(x, str) else tuple(x)
    return Rule(as_t(a), as_t(b), severity, category, title, mechanism, effect, management, patient,
                tuple(watch), tuple(evidence), tuple(covers))


BLEED_WATCH = ("unusual bruising", "bleeding gums or nosebleeds", "blood in urine or black, tarry stools",
               "vomiting blood", "severe headache or sudden weakness")

CURATED: List[Rule] = [
    # ------------------------------------------------------------------ warfarin
    R("warfarin", "fluconazole", MAJOR, PK, "Warfarin potentiation by fluconazole",
      "Fluconazole inhibits CYP2C9, the main clearance pathway of the more potent S-enantiomer of warfarin "
      "(and CYP3A4 for R-warfarin).",
      "Substantially raised INR and bleeding risk, typically within days of starting fluconazole, including single doses.",
      "Avoid if possible (consider a topical antifungal). If unavoidable, monitor INR closely (within 3-5 days) "
      "and anticipate a warfarin dose reduction.",
      "Fluconazole can make warfarin much stronger, which raises your risk of serious bleeding.",
      BLEED_WATCH, (SRC_WARFARIN_PI, SRC_FDA_CYP), ("pk", "qt")),
    R("warfarin", "miconazole", MAJOR, PK, "Warfarin potentiation by miconazole (including oral gel)",
      "Miconazole inhibits CYP2C9; clinically significant absorption occurs even from oral gel.",
      "Marked INR rise and bleeding events have been reported.",
      "Avoid the combination or monitor INR closely and reduce warfarin dose as needed.",
      "Miconazole (including the mouth gel) can make warfarin much stronger and cause bleeding.",
      BLEED_WATCH, (SRC_WARFARIN_PI,), ("pk",)),
    R("warfarin", "metronidazole", MAJOR, PK, "Warfarin potentiation by metronidazole",
      "Metronidazole inhibits the metabolism of S-warfarin.",
      "Large INR increases and bleeding.",
      "Prefer an alternative antibiotic; otherwise empirically reduce warfarin dose and check INR within 3-5 days.",
      "Metronidazole can make warfarin much stronger, increasing bleeding risk.",
      BLEED_WATCH, (SRC_WARFARIN_PI,), ("pk",)),
    R("warfarin", "sulfamethoxazole", MAJOR, PK, "Warfarin potentiation by sulfamethoxazole (co-trimoxazole)",
      "Sulfamethoxazole inhibits CYP2C9 and displaces warfarin from plasma proteins.",
      "Rapid INR rise; associated with hospitalisation for bleeding in older adults.",
      "Prefer an alternative antibiotic. If required, monitor INR within 3-5 days and reduce warfarin dose.",
      "This antibiotic can make warfarin much stronger, increasing bleeding risk.",
      BLEED_WATCH, (SRC_WARFARIN_PI,), ("pk",)),
    R("warfarin", "amiodarone", MAJOR, PK, "Warfarin potentiation by amiodarone",
      "Amiodarone inhibits CYP2C9 (and CYP3A4/1A2); effect builds over weeks due to its long half-life.",
      "INR rises progressively; bleeding risk.",
      "Reduce warfarin dose (commonly by 25-50%) when starting amiodarone and monitor INR weekly for several weeks; "
      "the effect persists for months after amiodarone is stopped.",
      "Amiodarone gradually makes warfarin stronger over several weeks, which can cause bleeding.",
      BLEED_WATCH, (SRC_WARFARIN_PI, SRC_FDA_CYP), ("pk",)),
    R("warfarin", ("rifampin",), MAJOR, PK, "Loss of warfarin effect with rifampin",
      "Rifampin strongly induces CYP2C9, CYP3A4 and CYP1A2, accelerating warfarin clearance.",
      "Sub-therapeutic INR and risk of thrombosis; INR may rise sharply when rifampin is stopped.",
      "Avoid if possible. Otherwise monitor INR frequently; large warfarin dose increases are usually needed, "
      "with reduction after rifampin is stopped.",
      "Rifampin can stop warfarin from working properly, raising the risk of blood clots.",
      ("leg swelling or pain", "chest pain or shortness of breath", "sudden weakness or trouble speaking"),
      (SRC_WARFARIN_PI,), ("pk",)),
    R("warfarin", ("carbamazepine", "phenytoin", "phenobarbital", "st john's wort"), MODERATE, PK,
      "Reduced warfarin effect with enzyme inducers",
      "Induction of warfarin metabolism (CYP2C9/CYP3A4).",
      "Lower INR and reduced anticoagulant protection; phenytoin can also transiently raise INR.",
      "Monitor INR closely on starting/stopping the inducer and adjust warfarin dose.",
      "This medicine can make warfarin less effective, so your blood test (INR) needs closer checking.",
      ("leg swelling or pain", "chest pain or shortness of breath"), (SRC_WARFARIN_PI,), ("pk",)),
    R("warfarin", "phytonadione", MODERATE, PD, "Vitamin K antagonises warfarin",
      "Vitamin K bypasses warfarin's inhibition of vitamin K epoxide reductase.",
      "Reduced anticoagulant effect (this is used therapeutically to reverse warfarin).",
      "Keep dietary/supplemental vitamin K intake consistent; do not start supplements without INR monitoring.",
      "Vitamin K reduces how well warfarin works. Keep your vitamin K intake steady.",
      (), (SRC_WARFARIN_PI,), ()),
    R("warfarin", "acetaminophen", MODERATE, PK, "INR increase with regular acetaminophen",
      "Regular acetaminophen use (>2 g/day for several days) interferes with vitamin K-dependent clotting factor synthesis.",
      "Dose-dependent INR increase.",
      "Occasional use is acceptable. For regular use above 2 g/day, monitor INR.",
      "Occasional acetaminophen (paracetamol) is fine, but taking it regularly can make warfarin stronger.",
      BLEED_WATCH, (SRC_WARFARIN_PI,), ()),
    R("warfarin", ("@nsaid", "aspirin"), MAJOR, PD, "Bleeding risk: warfarin with NSAIDs/aspirin",
      "Additive impairment of haemostasis (antiplatelet effect plus anticoagulation) and NSAID-induced "
      "gastrointestinal mucosal injury.",
      "Markedly increased risk of gastrointestinal and other major bleeding.",
      "Avoid NSAIDs; use acetaminophen for analgesia. Aspirin only if a clear indication exists (e.g., mechanical "
      "valve, recent ACS) with gastroprotection (PPI) and close monitoring.",
      "Taking these together greatly increases the risk of serious bleeding, especially in the stomach.",
      BLEED_WATCH, (SRC_WARFARIN_PI,), ("bleeding",)),
    # ------------------------------------------------------------------ DOACs
    R(("apixaban", "rivaroxaban"), ("ketoconazole", "itraconazole", "posaconazole", "voriconazole", "ritonavir",
                                    "cobicistat"), MAJOR, PK, "DOAC exposure increased by strong CYP3A4 + P-gp inhibitors",
      "Combined inhibition of CYP3A4 and P-glycoprotein reduces DOAC clearance.",
      "Increased anticoagulant exposure and bleeding risk.",
      "Rivaroxaban: avoid. Apixaban: reduce dose by 50% (avoid if already on 2.5 mg twice daily).",
      "This combination can raise blood thinner levels and increase bleeding risk.",
      BLEED_WATCH, ("Eliquis (apixaban) and Xarelto (rivaroxaban) US Prescribing Information",), ("pk",)),
    R(("apixaban", "rivaroxaban", "dabigatran", "edoxaban"), ("rifampin", "carbamazepine", "phenytoin",
                                                              "st john's wort"), MAJOR, PK,
      "Loss of DOAC effect with strong inducers",
      "Induction of CYP3A4 and/or P-glycoprotein lowers DOAC exposure substantially.",
      "Reduced anticoagulation and risk of stroke or venous thromboembolism.",
      "Avoid the combination; choose an alternative anticoagulant or non-inducing co-medication.",
      "This medicine can make your blood thinner stop working properly, raising clot and stroke risk.",
      ("sudden weakness or numbness", "trouble speaking", "leg swelling or pain", "shortness of breath"),
      ("Eliquis, Xarelto, Pradaxa and Savaysa US Prescribing Information",), ("pk",)),
    # ------------------------------------------------------------------ clopidogrel / tamoxifen prodrugs
    R("clopidogrel", ("omeprazole", "esomeprazole"), MAJOR, PK, "Reduced clopidogrel activation by omeprazole/esomeprazole",
      "Clopidogrel is a prodrug activated mainly by CYP2C19; omeprazole and esomeprazole inhibit CYP2C19.",
      "Lower active-metabolite exposure and reduced platelet inhibition; potential loss of protection against "
      "stent thrombosis and recurrent cardiovascular events.",
      "Avoid. If gastroprotection is needed, use pantoprazole or an H2-receptor antagonist (not cimetidine).",
      "Omeprazole/esomeprazole can stop clopidogrel from working properly. Ask about pantoprazole instead.",
      ("chest pain", "sudden weakness or trouble speaking"), (SRC_CLOPI_DSC,), ("pk",)),
    R("tamoxifen", ("paroxetine", "fluoxetine", "bupropion", "quinidine"), MAJOR, PK,
      "Reduced tamoxifen activation by strong CYP2D6 inhibitors",
      "Tamoxifen is converted by CYP2D6 to its principal active metabolite endoxifen; strong CYP2D6 inhibitors "
      "markedly reduce endoxifen concentrations.",
      "Potentially reduced efficacy of breast cancer treatment.",
      "Avoid strong CYP2D6 inhibitors; for depression or hot flushes consider venlafaxine or other agents with "
      "minimal CYP2D6 inhibition.",
      "This medicine may make tamoxifen less effective. Ask your oncology team about alternatives.",
      (), (SRC_FDA_CYP, "Tamoxifen US Prescribing Information"), ("pk",)),
    # ------------------------------------------------------------------ statins
    R(("simvastatin", "lovastatin"), ("ketoconazole", "itraconazole", "posaconazole", "voriconazole",
                                      "clarithromycin", "erythromycin", "ritonavir", "cobicistat", "gemfibrozil",
                                      "cyclosporine"), CONTRAINDICATED, PK,
      "Contraindicated: simvastatin/lovastatin with strong CYP3A4 inhibitors, gemfibrozil or cyclosporine",
      "Simvastatin and lovastatin are sensitive CYP3A4 substrates; these agents raise statin (acid) exposure "
      "many-fold (gemfibrozil and cyclosporine also via OATP1B1/glucuronidation inhibition).",
      "Myopathy and rhabdomyolysis, potentially with acute kidney injury.",
      "Contraindicated. Withhold the statin for the duration of a short antibiotic/antifungal course, or switch to "
      "a statin with less CYP3A4 dependence (e.g., pravastatin, rosuvastatin) at appropriate doses.",
      "This combination can cause severe muscle damage. Do not take them together.",
      ("unexplained muscle pain, tenderness or weakness", "dark (tea- or cola-coloured) urine"),
      (SRC_SIMVA_DSC, SRC_FDA_CYP), ("pk", "myopathy")),
    R(("simvastatin",), ("diltiazem", "verapamil", "dronedarone"), MODERATE, PK,
      "Simvastatin dose limit with diltiazem/verapamil/dronedarone",
      "Moderate CYP3A4 inhibition increases simvastatin exposure.",
      "Increased risk of myopathy.",
      "Do not exceed simvastatin 10 mg/day, or switch statin.",
      "Your statin dose may need to be lowered while taking this medicine.",
      ("unexplained muscle pain or weakness", "dark urine"), (SRC_SIMVA_DSC,), ("pk",)),
    R(("simvastatin",), ("amlodipine", "amiodarone"), MODERATE, PK,
      "Simvastatin dose limit with amlodipine/amiodarone",
      "Weak CYP3A4 inhibition increases simvastatin exposure.",
      "Increased risk of myopathy at higher simvastatin doses.",
      "Do not exceed simvastatin 20 mg/day, or switch statin.",
      "Your statin dose may need to stay low while taking this medicine.",
      ("unexplained muscle pain or weakness", "dark urine"), (SRC_SIMVA_DSC,), ("pk",)),
    R(("atorvastatin", "rosuvastatin", "pravastatin", "pitavastatin", "fluvastatin"), "gemfibrozil", MAJOR, PK,
      "Statin with gemfibrozil",
      "Gemfibrozil inhibits statin glucuronidation and OATP1B1 uptake, and adds intrinsic myotoxicity.",
      "Increased risk of myopathy and rhabdomyolysis.",
      "Avoid; if a fibrate is needed, fenofibrate is preferred.",
      "This combination increases the risk of muscle damage.",
      ("unexplained muscle pain or weakness", "dark urine"), ("Statin US Prescribing Information (gemfibrozil)",),
      ("pk", "myopathy")),
    R(("rosuvastatin", "atorvastatin", "pitavastatin"), "cyclosporine", MAJOR, PK, "Statin exposure increased by cyclosporine",
      "Cyclosporine inhibits OATP1B1 (and CYP3A4 / BCRP), increasing statin exposure several-fold.",
      "Increased risk of myopathy.",
      "Pitavastatin: contraindicated. Rosuvastatin: max 5 mg/day. Atorvastatin: avoid.",
      "This combination can raise statin levels and cause muscle damage.",
      ("unexplained muscle pain or weakness", "dark urine"), ("Statin US Prescribing Information (cyclosporine)",),
      ("pk", "myopathy")),
    R("@statin", "fenofibrate", MINOR, PD, "Statin with fenofibrate",
      "Additive myotoxic potential (much lower than with gemfibrozil).",
      "Small increase in myopathy risk.",
      "Generally acceptable; counsel on muscle symptoms.",
      "Rarely, this combination can cause muscle problems.",
      ("unexplained muscle pain or weakness",), ("Fenofibrate US Prescribing Information",), ("myopathy",)),
    # ------------------------------------------------------------------ serotonergic
    R("tramadol", ("@ssri", "@snri", "@tca"), MAJOR, "Pharmacokinetic + Pharmacodynamic",
      "Tramadol with SSRIs/SNRIs/TCAs: serotonin syndrome and seizures",
      "Additive serotonergic activity; tramadol lowers the seizure threshold; several antidepressants "
      "(fluoxetine, paroxetine, bupropion) also inhibit CYP2D6, reducing tramadol's analgesic activation and "
      "increasing parent-drug serotonergic exposure.",
      "Serotonin syndrome (agitation, hyperthermia, clonus, autonomic instability) and seizures.",
      "Avoid where possible; if used, use the lowest tramadol dose and monitor for serotonin toxicity. Consider a "
      "non-serotonergic analgesic.",
      "Taking these together can cause a dangerous reaction called serotonin syndrome, and seizures.",
      ("agitation or confusion", "fast heartbeat", "high fever or heavy sweating", "muscle twitching or stiffness",
       "seizures"), ("Tramadol (Ultram) US Prescribing Information", SRC_SEROTONIN), ("serotonin", "pk")),
    R("bupropion", "@maoi", CONTRAINDICATED, PD, "Bupropion with MAO inhibitors",
      "Bupropion increases noradrenergic and dopaminergic activity, which MAO inhibition amplifies.",
      "Hypertensive reactions.",
      "Contraindicated; allow at least 14 days between stopping an MAOI and starting bupropion.",
      "These must not be taken together because they can cause a dangerous rise in blood pressure.",
      ("severe headache", "chest pain", "very high blood pressure"), ("Bupropion US Prescribing Information",), ()),
    R("@maoi", "pseudoephedrine", CONTRAINDICATED, PD, "MAO inhibitors with sympathomimetics",
      "MAO inhibition prevents breakdown of noradrenaline released by indirect sympathomimetics.",
      "Hypertensive crisis.",
      "Contraindicated.",
      "These must not be taken together because they can cause a dangerous rise in blood pressure.",
      ("severe headache", "chest pain", "pounding heartbeat"), ("MAOI US Prescribing Information",), ()),
    # ------------------------------------------------------------------ cardiovascular
    R("@pde5_inhibitor", "@nitrate", CONTRAINDICATED, PD, "PDE5 inhibitors with nitrates",
      "Both increase cGMP-mediated vasodilation (nitrates via NO donation, PDE5 inhibitors by blocking cGMP breakdown).",
      "Profound, potentially fatal hypotension.",
      "Contraindicated. Do not give nitrates within 24 h of sildenafil/vardenafil or 48 h of tadalafil.",
      "Taking these together can cause a sudden, dangerous drop in blood pressure. Never combine them.",
      ("dizziness or fainting", "chest pain"), ("Viagra, Cialis and Levitra US Prescribing Information",),
      ("hypotension",)),
    R(("@pde5_inhibitor", "@nitrate"), "riociguat", CONTRAINDICATED, PD, "Riociguat with PDE5 inhibitors or nitrates",
      "Additive stimulation of the NO-sGC-cGMP pathway.",
      "Severe hypotension.",
      "Contraindicated.",
      "These must not be taken together because blood pressure can drop dangerously.",
      ("dizziness or fainting",), ("Adempas (riociguat) US Prescribing Information",), ("hypotension",)),
    R("sacubitril", "@acei", CONTRAINDICATED, PD, "Sacubitril/valsartan with ACE inhibitors",
      "Combined neprilysin and ACE inhibition markedly increases bradykinin.",
      "Angioedema.",
      "Contraindicated. Stop the ACE inhibitor at least 36 hours before starting sacubitril/valsartan.",
      "These must not be taken together because they can cause serious swelling of the face and throat.",
      ("swelling of the lips, tongue or throat", "difficulty breathing"),
      ("Entresto (sacubitril/valsartan) US Prescribing Information",), ("raas",)),
    R("digoxin", ("amiodarone", "verapamil", "clarithromycin", "quinidine", "dronedarone", "itraconazole"), MAJOR, PK,
      "Digoxin toxicity with P-glycoprotein inhibitors",
      "Inhibition of P-glycoprotein-mediated renal and intestinal digoxin efflux.",
      "Raised digoxin concentrations (often 50-100%) with risk of toxicity: arrhythmia, bradycardia, nausea, visual "
      "disturbance.",
      "Measure serum digoxin before starting; reduce digoxin dose (typically by 30-50%) and re-check levels.",
      "This medicine can raise digoxin to toxic levels. Your digoxin dose may need to be reduced.",
      ("nausea or vomiting", "loss of appetite", "blurred or yellow-tinted vision", "slow or irregular heartbeat",
       "confusion"), ("Lanoxin (digoxin) US Prescribing Information", SRC_FDA_CYP), ("pk",)),
    # ------------------------------------------------------------------ lithium
    R("lithium", ("@thiazide", "@acei", "@arb", "@nsaid"), MAJOR, PK, "Lithium toxicity",
      "Reduced renal lithium clearance (sodium depletion with thiazides; reduced GFR / increased proximal "
      "reabsorption with ACE inhibitors, ARBs and NSAIDs).",
      "Lithium accumulation and toxicity (tremor, ataxia, confusion, arrhythmia, renal injury).",
      "Avoid if possible. Otherwise reduce lithium dose and check serum lithium within 5-7 days of starting or "
      "changing the interacting drug.",
      "This medicine can raise lithium in your blood to toxic levels. Your lithium level will need checking.",
      ("worsening hand tremor", "diarrhoea or vomiting", "unsteadiness", "confusion or unusual drowsiness"),
      ("Lithium US Prescribing Information",), ("lithium", "renal_nsaid")),
    R("lithium", "@loop_diuretic", MODERATE, PK, "Lithium with loop diuretics",
      "Sodium and volume depletion can reduce lithium clearance (less than with thiazides).",
      "Possible rise in lithium concentration.",
      "Monitor serum lithium and hydration status.",
      "This medicine may raise your lithium level; it should be checked.",
      ("worsening tremor", "unsteadiness", "confusion"), ("Lithium US Prescribing Information",), ("lithium",)),
    # ------------------------------------------------------------------ narrow-index specifics
    R("tizanidine", ("fluvoxamine", "ciprofloxacin"), CONTRAINDICATED, PK, "Tizanidine with strong CYP1A2 inhibitors",
      "Tizanidine is a sensitive CYP1A2 substrate; fluvoxamine and ciprofloxacin raise its AUC ~10-30-fold.",
      "Severe hypotension, bradycardia and excessive sedation.",
      "Contraindicated.",
      "These must not be taken together because blood pressure can drop dangerously and cause heavy sedation.",
      ("dizziness or fainting", "extreme drowsiness", "slow heartbeat"),
      ("Zanaflex (tizanidine) US Prescribing Information", SRC_FDA_CYP), ("pk", "cns")),
    R("colchicine", ("clarithromycin", "ketoconazole", "itraconazole", "ritonavir", "cobicistat", "cyclosporine",
                     "verapamil", "diltiazem"), MAJOR, PK, "Colchicine toxicity with CYP3A4/P-gp inhibitors",
      "Inhibition of CYP3A4 and/or P-glycoprotein markedly increases colchicine exposure.",
      "Colchicine toxicity, which can be fatal (myelosuppression, neuromuscular toxicity, multi-organ failure).",
      "Reduce colchicine dose per label; contraindicated in patients with renal or hepatic impairment.",
      "This combination can cause colchicine poisoning. Your dose may need to be reduced or the combination avoided.",
      ("severe diarrhoea or vomiting", "muscle weakness or pain", "numbness or tingling", "unusual bleeding or bruising"),
      ("Colcrys (colchicine) US Prescribing Information",), ("pk",)),
    R("repaglinide", "gemfibrozil", CONTRAINDICATED, PK, "Repaglinide with gemfibrozil",
      "Gemfibrozil (via its glucuronide) inhibits CYP2C8 and OATP1B1, raising repaglinide exposure ~8-fold.",
      "Prolonged, severe hypoglycaemia.",
      "Contraindicated.",
      "Taking these together can cause dangerously low blood sugar.",
      ("shakiness, sweating or fast heartbeat", "confusion", "fainting"),
      ("Prandin (repaglinide) US Prescribing Information",), ("pk", "hypoglycemia")),
    R("lamotrigine", "valproate", MAJOR, PK, "Lamotrigine with valproate",
      "Valproate inhibits lamotrigine glucuronidation, roughly doubling its half-life.",
      "Increased lamotrigine levels and higher risk of serious rash (SJS/TEN).",
      "Use the valproate-specific lamotrigine titration schedule (approximately half the usual dose).",
      "Valproate raises lamotrigine levels and increases the risk of a serious skin rash.",
      ("any new skin rash", "blistering or peeling skin", "mouth sores", "fever"),
      ("Lamictal (lamotrigine) US Prescribing Information",), ("pk",)),
    R(("allopurinol", "febuxostat"), ("azathioprine", "mercaptopurine"), MAJOR, PK,
      "Thiopurine toxicity with xanthine oxidase inhibitors",
      "Xanthine oxidase inactivates mercaptopurine; inhibition increases active thioguanine nucleotides.",
      "Severe, potentially fatal myelosuppression.",
      "Febuxostat: contraindicated. Allopurinol: reduce azathioprine/mercaptopurine to one-third to one-quarter "
      "of the usual dose with close blood count monitoring.",
      "This combination can severely lower blood cell counts. Doses must be adjusted by your specialist.",
      ("fever or signs of infection", "unusual bleeding or bruising", "extreme tiredness"),
      ("Uloric, Zyloprim and Imuran US Prescribing Information",), ("pk",)),
    R("methotrexate", ("trimethoprim", "sulfamethoxazole"), MAJOR, "Pharmacokinetic + Pharmacodynamic",
      "Methotrexate with trimethoprim / co-trimoxazole",
      "Additive antifolate effect and reduced renal methotrexate clearance.",
      "Bone marrow suppression and pancytopenia, even with low-dose methotrexate.",
      "Avoid; choose an alternative antibiotic.",
      "This antibiotic can make methotrexate toxic to your blood cells.",
      ("fever or sore throat", "mouth ulcers", "unusual bleeding or bruising"),
      ("Methotrexate US Prescribing Information",), ("potassium",)),
    R("methotrexate", "@nsaid", MODERATE, PK, "Methotrexate with NSAIDs",
      "NSAIDs reduce renal methotrexate clearance.",
      "Increased methotrexate toxicity, particularly with high-dose (oncology) regimens or renal impairment.",
      "Low-dose weekly methotrexate: generally acceptable with monitoring of renal function and blood counts. "
      "High-dose methotrexate: avoid.",
      "Anti-inflammatory painkillers can raise methotrexate levels; your doctor may monitor blood tests.",
      ("mouth ulcers", "fever", "unusual bruising"), ("Methotrexate US Prescribing Information",), ("renal_nsaid",)),
    R("methotrexate", "@penicillin", MODERATE, PK, "Methotrexate with penicillins",
      "Penicillins reduce renal tubular secretion of methotrexate.",
      "Increased methotrexate exposure and toxicity.",
      "Monitor blood counts and methotrexate toxicity, particularly with higher methotrexate doses.",
      "This antibiotic may raise methotrexate levels.",
      ("mouth ulcers", "fever", "unusual bruising"), ("Methotrexate US Prescribing Information",), ()),
    # ------------------------------------------------------------------ alcohol
    R("@disulfiram_like", "alcohol", MAJOR, PK, "Disulfiram-like reaction with alcohol",
      "Inhibition of aldehyde dehydrogenase leads to acetaldehyde accumulation (directly for disulfiram; "
      "metronidazole/tinidazole labels warn of a similar reaction).",
      "Flushing, nausea, vomiting, tachycardia, hypotension.",
      "Avoid alcohol during treatment and for at least 3 days after metronidazole/tinidazole (14 days after disulfiram).",
      "Do not drink alcohol with this medicine (and for a few days afterwards); it can make you very unwell.",
      ("flushing", "pounding headache", "nausea and vomiting", "fast heartbeat"),
      ("Flagyl, Tindamax and Antabuse US Prescribing Information",), ("cns",)),
    R("metformin", "alcohol", MODERATE, PD, "Metformin with alcohol",
      "Alcohol potentiates metformin's effect on lactate metabolism.",
      "Increased risk of lactic acidosis with excessive or binge drinking.",
      "Advise against excessive or binge alcohol intake.",
      "Heavy drinking while taking metformin can cause a rare but serious condition called lactic acidosis.",
      ("unusual muscle pain", "trouble breathing", "stomach pain with extreme tiredness"),
      ("Glucophage (metformin) US Prescribing Information",), ()),
    # ------------------------------------------------------------------ hormonal contraception
    R("@hormonal_contraceptive", ("rifampin", "rifabutin", "carbamazepine", "phenytoin", "phenobarbital",
                                  "st john's wort", "efavirenz"), MAJOR, PK, "Contraceptive failure with enzyme inducers",
      "Induction of CYP3A4 accelerates ethinyl estradiol and progestin metabolism.",
      "Reduced contraceptive efficacy and unintended pregnancy.",
      "Use a non-hormonal or non-affected method (e.g., copper or levonorgestrel IUD) during and for 28 days "
      "after the inducer.",
      "This medicine can stop your birth control pill from working. Use another method of contraception.",
      ("breakthrough bleeding",), ("FSRH Clinical Guidance: Drug interactions with hormonal contraception",
                                   SRC_FDA_CYP), ("pk",)),
]
