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

## Run 2: 2026-11-02 (commit `d41d942`, [run 41426010219](https://github.com/TEKURU-ZENO/BioGPT-DDI/actions/runs/41426010219))

Same engine as run 1, so the scores are unchanged. This run confirmed the evaluator fixes:
- KEGG kappa now reads "n/a".
- DDInter coverage excluding severity-"Unknown" records is **29.9%** (28.5–31.3%).

Its `--debug` log showed that the live FDA CYP page is a single drug-per-row table, with roles written as text
such as "2D6 moderate inhibitor". The parser was rewritten for that layout in commit `5ec1374`; it will be
measured in run 4.

## Run 3: 2026-11-02 (commit `4a6984b`, [run 41428509966](https://github.com/TEKURU-ZENO/BioGPT-DDI/actions/runs/41428509966))

This run measures the label-backed rule additions and the AUC-extractor fix.

| Metric | Run 1 | Run 3 |
|---|---|---|
| DDInter coverage, all pairs | 15.8% | **16.6%** (15.8–17.4%) |
| DDInter coverage, excluding "Unknown" | 29.9% | **31.4%** (30.0–32.8%) |
| DDInter Major pairs detected | 68.7% | **70.2%** (67.3–73.1%) |
| DDInter Major pairs graded Major | 48.6% | **51.3%** (48.1–54.3%) |
| DDInter Moderate pairs detected | 20.7% | **22.4%** (20.9–23.9%) |
| Weighted kappa vs DDInter | 0.230 | **0.242** (0.224–0.259) |
| False alerts on sampled negatives | 12.2% | 12.3% (unchanged) |
| KEGG contraindicated pairs detected | 78.2% | **81.7%** (76.7–86.3%) |
| KEGG contraindicated pairs graded Contraindicated | 37.0% | **39.3%** (33.2–45.4%) |

These are modest, consistent gains with no rise in false alerts, as expected from about 40 targeted rules against
about 8,000 reference pairs. Breadth is still the main limit: 11.9% of DDInter drugs are in the lexicon.

**Exposure (AUC) estimates.** Because of the extractor fix, label observations rose from 181 to 262 and unique
pairs from 95 to 136. The pair set changed, so run 1 and run 3 are not directly comparable.

| Metric | Run 3 |
|---|---|
| Coverage of observed interactions | **37.4%** (run 1: 27.4%) |
| Pairs scored | 38 |
| GMFE | 1.57 |
| Within 2-fold | 81.6% |
| Under- / over-predicted by more than 2-fold | **7 / 0** |

The errors are one-sided. The class model caps the fraction metabolised by one enzyme at 0.9, so it cannot reach
the magnitudes seen with extremely sensitive substrates:
- buspirone + itraconazole: 19× observed vs 5.3× predicted
- simvastatin + diltiazem: 6.7× vs 2.5×
- sildenafil + ritonavir: 11× vs 5.3×

The principled fix is drug-specific fm values for those substrates. They must be fitted on the calibration half only
and then reported on the holdout half. The extractor fix also corrected the earlier sirolimus + verapamil outlier,
from 0.67× to 1.5×.

## Run 4: 2026-11-02 (commit `3706c7e`, [run 41431814303](https://github.com/TEKURU-ZENO/BioGPT-DDI/actions/runs/41431814303))

The FDA CYP-table parser fix worked: the import now reads roles for **198 drugs** (runs 1–3: 26).

| Metric | Hand-curated lexicon | + FDA-table roles |
|---|---|---|
| DDInter coverage, excluding "Unknown" | 31.4% | 32.2% |
| DDInter Major pairs detected | 70.2% | 71.0% |
| DDInter Moderate pairs detected | 22.4% | 23.3% |
| Weighted kappa | 0.242 | 0.246 |
| False alerts on sampled negatives | 12.3% | 12.4% |
| KEGG contraindicated pairs detected | 81.7% | 83.6% |
| PK coverage of observed interactions | 37.4% | 38.4% |
| PK GMFE / within 2-fold | 1.57 / 81.6% | 1.58 / 80.0% |

**This understates the breadth gain, because of a measurement flaw.** The references were built *before* the FDA
import and keep only drugs the lexicon knew at that moment. The drugs the FDA table adds could therefore never
appear in the reference set; the table above only shows extra roles for drugs already present.

**Fixed for run 5:**
- The workflow imports the FDA table first and builds the references with the expanded lexicon.
- The "hand-curated only" evaluation switches the imported roles off (`DDI_DISABLE_GENERATED_ROLES=1`), so both
  columns score the same pairs.
- The merge summary (drugs added, roles enriched, FDA-vs-curated conflicts) is now printed to the log.

Run 5 numbers will not be comparable to runs 1–4, because the reference set grows.

## Run 5: 2026-11-02 (commit `f385117`, [run 41436292391](https://github.com/TEKURU-ZENO/BioGPT-DDI/actions/runs/41436292391))

This is the first fair breadth measurement. The FDA table was imported first, the references were built with the
expanded lexicon, and both columns score exactly the same pairs. **These numbers are not comparable with runs 1–4**,
because the reference set grew to include the new drugs.

**FDA merge.** Roles were parsed for 198 drugs: **119 drugs added** as mechanism-only profiles, 24 existing drugs
enriched, and 5 conflicts with hand-curated roles (resolved below). Lexicon coverage of DDInter drugs rose from
231/1,939 (11.9%) to **324/1,939 (16.7%)**.

**References.**
- DDInter: 16,249 pairs, including 1,000 sampled negatives.
- KEGG: 9,264 pairs (330 of 350 ingredients mapped).
- FDA labels: 703 AUC observations, giving 346 unique pairs.

| Metric | Hand-curated only | + FDA-table roles |
|---|---|---|
| DDInter coverage, excluding "Unknown" | 13.6% (12.9–14.3%) | **27.4%** (26.5–28.2%) |
| DDInter Major pairs detected | 24.7% | **48.6%** (46.7–50.4%) |
| DDInter Major pairs graded Major | 18.0% | **29.4%** (27.7–31.0%) |
| DDInter Moderate pairs detected | 10.2% | **20.7%** |
| Weighted kappa | 0.064 | **0.136** (0.127–0.145) |
| False alerts on sampled negatives | 6.1% | 9.3% |
| KEGG contraindicated pairs detected | 42.3% | **67.4%** (63.0–71.3%) |
| KEGG contraindicated pairs graded Contraindicated | 20.4% | 20.4% |
| PK coverage of observed interactions | 12.8% | **33.3%** |
| PK pairs scored | 38 | 103 |
| PK GMFE / within 2-fold | 1.57 / 81.6% | 1.75 / 74.8% |
| PK under- / over-predicted by > 2-fold | 7 / 0 | 16 / 10 |

**Reading.**
1. On the same pairs, the FDA-table roles roughly **double detection**: Major detected 24.7% → 48.6%, KEGG
   contraindications 42.3% → 67.4%, PK coverage 12.8% → 33.3%. This is the breadth gain run 4 could not see.
2. **Detection now outpaces grading.** Mechanism-only drugs have no curated rules, so they are flagged but rarely
   graded Major. Only 29% of DDInter Major pairs are graded Major, and contraindication grading did not move.
   Curated rules for the new drugs' high-severity pairs are the next lever.
3. **The cost is precision.** False alerts rose from 6.1% to 9.3% on sampled negatives, mostly class-level CYP
   findings for drugs with no curated context.
4. **The PK error became two-sided** (16 under, 10 over). The class-level sensitivity of the new drugs is coarse.
   Drug-specific fm values fitted on the calibration half are the fix.

**Conflicts resolved (lexicon aligned with the FDA table, its cited source):**
- cyclosporine as a CYP3A4 inhibitor: moderate → weak
- omeprazole as a CYP2C19 inhibitor: moderate → weak
- nortriptyline as a CYP2D6 substrate: sensitive → moderate
- warfarin as a CYP2C9 substrate: sensitive → moderate (still narrow-therapeutic-index, so warfarin interactions keep
  their severity)
- ticagrelor as a CYP3A4 substrate: moderate → sensitive

Consequence: omeprazole no longer phenoconverts CYP2C19, so tests and the README example were updated. Clopidogrel +
omeprazole remains a curated Major interaction.

### Changes made in response to run 5 (measured from run 6 onwards)

- **Label-based CYP3A restrictions.** 15 drugs were added whose US labels contraindicate or advise avoiding CYP3A
  perpetrators: lurasidone, naloxegol, lomitapide, tolvaptan, conivaptan, ivabradine, ranolazine, alfuzosin,
  eletriptan, flibanserin, pimozide, ergotamine, dihydroergotamine, avanafil and suvorexant. Eplerenone was also
  tagged. The rule is keyed on the perpetrator's CYP3A *strength*, not a name list, so strong inhibitors added by
  the FDA import are covered automatically.
- **Drug-specific exposure parameters.** The CR-IR method is fitted on the calibration half of the FDA-label
  observations. On an illustrative fixture it lowered the holdout GMFE in all five tested splits (e.g.
  1.88 → 1.45). Run 6 will report the real FDA-label holdout.
- **Curation worklist.** The evaluator now ranks the drugs most often involved in reference Major or
  Contraindicated pairs that the engine grades lower. The workflow also logs the names of the drugs added from the
  FDA table, so the next round of rules targets the largest gaps.

## Run 6: 2026-11-02 (commit `461fbf3`, [run 41443538474](https://github.com/TEKURU-ZENO/BioGPT-DDI/actions/runs/41443538474))

The reference set grew slightly: the lexicon covers 330 of 1,939 DDInter drugs (17.0%), with 16,548 DDInter pairs
and 732 label AUC observations. Compare with run 5's "+ FDA roles" column with that caveat.

**Severity (with FDA-table roles), effect of the label-based CYP3A rules:**

| Metric | Run 5 | Run 6 |
|---|---|---|
| DDInter coverage, excluding "Unknown" | 27.4% | 27.6% |
| DDInter Major pairs detected | 48.6% | 49.7% |
| DDInter Major pairs graded Major | 29.4% | **31.6%** (29.9–33.4%) |
| Weighted kappa | 0.136 | 0.141 |
| False alerts on sampled negatives | 9.3% | 9.7% |
| KEGG contraindicated pairs detected | 67.4% | 68.3% |
| KEGG contraindicated pairs graded Contraindicated | 20.4% | **27.3%** (23.4–31.4%) |

**Exposure, CR-IR fitting (negative result).** The fit used 187 calibration pairs, but only 54 could be linked to
an enzyme (45 inhibition, 9 induction). It produced CR for 36 victims, IR for 19 inhibitors and IC for 3 inducers.

| GMFE (within 2-fold) | Calibration half | **Holdout half** |
|---|---|---|
| FDA roles, class parameters | 1.76 (76.8%) | **1.70** (71.7%) |
| FDA roles + fitted parameters | 1.47 (82.1%) | **1.84** (73.6%) |

The fit improved the data it was trained on but **worsened the holdout**: it overfitted, with mostly one observation
per parameter and too little shrinkage. Fitted parameters are therefore not used by default; the file is generated
only in CI and is git-ignored.

**Fixed after run 6:**
- The shrinkage strength is now chosen by 5-fold cross-validation *inside* the calibration half, and "no fitting"
  (class values) is one of the options. Parameters are written only if a fitted strength beats the class model in
  cross-validation. The holdout remains the judge.
- The FDA table has combination rows such as "lopinavir and ritonavir", which the import was turning into a single
  "drug". They now map to their ingredients.

**Curation worklist** (DDInter Major/Contraindicated pairs graded lower by the engine, drugs most often involved):
- Oncology kinase inhibitors: crizotinib, ceritinib, vemurafenib, ivosidenib, dasatinib, venetoclax, ibrutinib,
  lorlatinib, entrectinib, selpercatinib. These are mostly QT and CYP3A interactions.
- Teriflunomide, eliglustat, hydrocodone, erythromycin, cilostazol, tacrolimus, ivacaftor, tamoxifen,
  hydroxychloroquine, apalutamide/enzalutamide, bupropion, ondansetron.

The KEGG worklist is dominated by ticagrelor, rifampin, colchicine and tadalafil. There, Japanese labels
contraindicate what US labels grade as "avoid" or a dose limit, so these are largely jurisdiction differences, not
errors.
