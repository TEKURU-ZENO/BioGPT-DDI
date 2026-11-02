# Validation results

## Run 1: 2026-11-02 (commit `07843ac`, [workflow run 41416594718](https://github.com/TEKURU-ZENO/BioGPT-DDI/actions/runs/41416594718))

The engine was evaluated with its DDInter evidence layer and learned model switched off.

### References built

| Reference | Result |
|---|---|
| DDInter | 222,383 records. **231 of 1,939 DDInter drugs (11.9%) are in the lexicon.** 8,074 interacting pairs between lexicon drugs, plus 1,000 sampled negatives. |
| KEGG DDI | 226 of 231 ingredients mapped. 4,096 pairs: 262 contraindicated (CI), 3,834 precaution (P). |
| FDA labels (AUC) | 181 extracted observations, collapsing to 95 unique pairs (73 with a change of 25% or more). |
| ONC lists | Not run, because the transcription is still empty. |
| FDA CYP tables | **Parser under-performed:** roles for only 26 drugs, so coverage did not change. Fix in progress (see below). |

### Severity: DDInter (pharmacist-curated)

| Metric | Value (95% CI) |
|---|---|
| Coverage, all listed pairs | 15.8% (14.9–16.6%) |
| Coverage, pairs with a graded severity | ~30% (computed from the per-grade rows; reported directly from run 2 onwards) |
| DDInter **Major** pairs detected (any finding) | **68.7%** (65.6–71.6%) |
| DDInter Major pairs graded Major by the engine | 48.6% (45.4–51.5%) |
| DDInter Moderate pairs detected | 20.7% (19.1–22.2%) |
| Quadratic-weighted kappa | **0.23** (0.21–0.25), "fair" agreement |
| False alerts on sampled negatives | 12.2% (approximate: the negatives assume DDInter is complete) |

### Contraindications: KEGG DDI (package inserts)

| Metric | Value (95% CI) |
|---|---|
| KEGG contraindicated (CI) pairs detected | **78.2%** (73.3–83.2%) |
| CI pairs graded Contraindicated by the engine | 37.0% (31.7–42.7%) |
| Precaution (P) pairs detected | 41.0% (39.4–42.6%) |
| Kappa | Not meaningful, because KEGG grades only one level. Run 1 printed 0.000 due to an evaluator bug, now fixed. |

KEGG's CI flags follow Japanese labelling, which contraindicates more combinations than US labelling. A low
"engine Contraindicated" rate is therefore partly a difference in regulatory jurisdiction, not purely a miss.

### Exposure estimates: FDA label AUC ratios

| Metric | All pairs | Holdout half |
|---|---|---|
| Coverage of observed interactions | **27.4%** | 27.0% |
| Pairs scored | 21 | 11 |
| GMFE | **1.49** | 1.58 |
| Within 2-fold | **85.7%** | 81.8% |
| Within 1.25-fold | 38.1% | 27.3% |
| Observed inside stated range | 66.7% | 54.5% |
| FDA magnitude-category agreement | 42.9% | 36.4% |

The extraction is heuristic. Before tuning anything, audit the outliers against the label text. For example,
sirolimus + verapamil was extracted as 0.67×, which disagrees with the expected increase in sirolimus exposure, so
it is probably an extraction error.

### What the numbers say

1. **Where the engine has rules, the estimates are reasonable:** GMFE about 1.5, and over 80% within 2-fold.
   **Breadth is the binding constraint.** About 12% of DDInter's drugs are in the lexicon, and among those, under a
   third of graded interactions are detected.
2. **Largest systematic gaps among high-severity misses:**
   - alcohol combinations (CNS depression, hypotension, hepatotoxicity)
   - bupropion and other seizure-threshold-lowering combinations
   - "possible / conditional" QT-risk drugs (only "known risk" is modelled)
   - hyperkalaemia via calcineurin inhibitors and aliskiren
   - theophylline with beta-blockers
   - ticagrelor with strong CYP3A inhibitors (labelled "avoid" in the US; the engine says Moderate)
   - P-gp-mediated colchicine combinations
3. **The exposure model is calibrated but narrow.** It covers about a quarter of observed interactions. Missing
   CYP2C8 and CYP2B6 roles (e.g. clopidogrel → repaglinide, bupropion) are exactly what the FDA-table import should
   add once its parser is fixed.

### Next run

- The FDA CYP table parser now handles title rows, ragged rows and rowspans, and the workflow prints each table's
  structure (`--debug`) so the live layout can be checked.
- The evaluator now reports coverage excluding "Unknown"-severity records, and prints kappa as n/a when a
  reference has a single grade.

### Changes made in response to run 1 (measured from run 3 onwards)

These cover misses where the **US label** is explicit. KEGG findings that reflect only Japanese labelling were not
adopted.

- **Contraindicated:** posaconazole + atorvastatin; ritonavir + amiodarone, dronedarone, flecainide, quinidine,
  triazolam, midazolam or St John's wort; dronedarone + strong CYP3A inhibitors; riociguat + dipyridamole or
  theophylline.
- **Major ("avoid"):** ticagrelor + strong CYP3A inhibitors or inducers; aliskiren + cyclosporine or itraconazole;
  calcineurin inhibitor + potassium-sparing diuretic; bupropion + other seizure-threshold-lowering drugs.
- **Moderate:**
  - acetaminophen + regular alcohol
  - methotrexate + aspirin
  - alcohol + CNS-active non-sedatives (SSRIs, SNRIs, bupropion, antiepileptics, antipsychotics)
  - alcohol + vasodilators
  - additive seizure-threshold lowering
- **Tags:** calcineurin inhibitors now carry potassium retention, so they are caught by the RAAS hyperkalaemia rule.
- **FDA-label AUC extractor:** the magnitude is now the one nearest the "AUC" mention (before or after it), the
  direction comes from the verb nearest that magnitude, and confidence-level percents ("90% CI") are ignored. Run 1
  missed "2.2-fold higher … AUC" phrasing and could mis-assign direction.
