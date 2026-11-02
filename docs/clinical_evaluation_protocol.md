# Clinical evaluation protocol (draft)

The automated gold standard (`eval/gold_standard.csv`) is a regression set the developers assembled from product
labelling. It shows that the engine reproduces documented interactions, but it is not independent validation. This
protocol describes the study needed before anyone could claim clinical usefulness.

## Objectives

1. **Safety.** Estimate the engine's sensitivity for clinically significant (Major or Contraindicated) interactions,
   judged by independent clinical pharmacists.
2. **Agreement.** Estimate agreement between the engine's severity and a pharmacist consensus grading, and compare it
   with the agreement between pharmacists themselves.
3. **Explanation quality.** Assess whether mechanisms, management advice and citations are accurate and supported.
4. **Alert burden.** Estimate the false-alert rate on realistic medication lists.

## Sample

- **Pair set A (enriched):** 300 drug pairs, stratified by expected severity. About 100 come from the ONC
  high-priority DDI list and FDA safety communications, 100 are moderate or minor pairs from DDInter, and 100 are
  random pairs of commonly prescribed drugs, mostly non-interacting.
- **Regimen set B (realistic):** 100 de-identified medication lists from older adults taking 5 or more drugs. Use
  publicly available or IRB-approved data, with age and eGFR where available.
- Exclude pairs where either drug is outside the knowledge base, and report how many were excluded. Coverage is
  itself an outcome.

## Reference standard

- Three clinical pharmacists work independently and are blinded to the engine's output. Each grades every pair as
  None / Minor / Moderate / Major / Contraindicated, using any licensed references they normally use.
- Consensus is the median grade. Pairs with a spread of more than one grade go to adjudication by discussion.
- Report inter-rater agreement (quadratic-weighted kappa) before consensus.

## Outcomes and analysis

| Outcome | Metric | Target |
|---|---|---|
| Safety-critical sensitivity | Engine grade ≥ Major when consensus ≥ Major (with 95% CI) | ≥ 0.95, lower CI bound ≥ 0.90 |
| Severity agreement | Quadratic-weighted kappa, engine vs consensus | Not inferior to median pharmacist-vs-consensus kappa |
| Under-calling | Share of pairs where engine < consensus by ≥ 2 grades | ≤ 2% |
| False alerts | Engine ≥ Moderate when consensus = None | Reported; target ≤ 10% |
| Explanation accuracy | Pharmacist rating of mechanism / management (1-5) and citation support (yes/no per claim) | Mean ≥ 4; ≥ 95% of citations support their claim |
| Patient-context alerts (set B) | Precision of renal / age / PGx alerts judged by pharmacists | Reported |

Compute the metrics with `python -m scripts.evaluate --reference consensus.csv`, where `consensus.csv` has columns
`drug1,drug2,severity`.

## Error analysis

Classify every under-call by its root cause:
1. The drug is missing from the lexicon.
2. The synonym or normalisation failed.
3. A curated rule is missing.
4. The mechanism data is wrong or incomplete.
5. The severity mapping is wrong.
6. The reference standard is debatable.

Feed each fix back into `eval/gold_standard.csv` so that it cannot regress.

## Ethics and limitations

- Use only de-identified data, and obtain IRB/ethics review if real patient regimens are used.
- The engine is a research prototype. No output may inform care during the study.
- Severity scales differ between compendia (e.g. Lexicomp, Micromedex). State the scale that was used.
