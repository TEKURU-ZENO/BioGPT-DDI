# Validation

Latest measured results: [`validation_results.md`](validation_results.md).

BioGPT-DDI is validated at three levels. Only the second and third use evidence this project did not write.

## 1. Internal regression set (authored here)

`eval/gold_standard.csv`: 78 pairs from product labelling and FDA safety communications. CI fails if any
safety-critical pair (Major or Contraindicated) is missed. This shows the rules fire. **It does not show
generalisation.**

## 2. Independent severity references

| Reference | Builder | Authored by | Scale | What it measures |
|---|---|---|---|---|
| DDInter 2.0 | `scripts/references/ddinter.py` | Clinical pharmacist team (Xiong et al., NAR) | Major / Moderate / Minor / Unknown | Coverage, severity agreement (weighted kappa), under-calls; false alerts on sampled negatives |
| KEGG DDI | `scripts/references/kegg.py` | Extracted from package inserts (KEGG MEDICUS) | CI (contraindicated) / P (precaution) | Recall of contraindications; detection of precautions |
| ONC high/low-priority lists | `scripts/references/onc.py` | Expert panel (Phansalkar et al., JAMIA 2012/2013) | must-alert / non-interruptive | Must-catch recall and over-alerting |

The scales are harmonised before scoring. DDInter and ONC have no "Contraindicated" grade, so the engine's
Contraindicated counts as Major against them.

**Circularity guard.** The engine can use DDInter as an evidence layer and a learned model as a signal layer.
`scripts/evaluate.py` switches both off, so the engine is scored only on its own curated and mechanism layers.

**Caveats.**
- DDInter lists interacting pairs only. "Negatives" are pairs of DDInter-covered drugs that it does not list
  together, which assumes DDInter is complete, so the false-alert rate is approximate.
- KEGG is licensed for academic use only, and DDInter for non-commercial use. Built references live only in
  short-lived workflow artifacts and are git-ignored.
- The ONC pairs must be transcribed from the papers into `eval/references/onc_transcription.csv`. They are
  deliberately not typed from memory.

## 3. Exposure (AUC) estimates

`scripts/evaluate_pk.py` compares the static-model estimates with observed AUC ratios from:
- **FDA labels** (sections 7 and 12.3, via openFDA): `scripts/references/pk_labels.py`. Heuristic extraction;
  every row keeps its source sentence, and the report lists the largest disagreements to audit first.
- **Published compilations** such as the CR/IR tables (Ohno 2007; Hisaka 2009; AAPS J 2015) or PK-DB exports:
  `scripts/references/pk_table.py`.

The University of Washington DIDB, which Certara now owns, is subscription-only and is not used.

Metrics:
- Geometric mean fold error (GMFE).
- Share of predictions within 1.25, 1.5 and 2-fold.
- Share of observations inside the stated plausible range.
- FDA magnitude-category agreement.
- Coverage of observed interactions.

`--holdout-seed` splits pairs into calibration and holdout halves. Tune any drug-specific parameters on the
calibration half only.

## 4. Breadth

`scripts/import_fda_cyp_table.py` imports the FDA tables of CYP and P-gp substrates, inhibitors and inducers. It
adds mechanism-only profiles for drugs not in the lexicon and fills missing roles for existing ones. It never
overwrites hand-curated roles; disagreements are listed for review. The validation workflow reports coverage
before and after this import.

## Running

The `Independent validation` GitHub Actions workflow (on demand and weekly) builds every reference with internet
access. It runs the evaluations before and after the FDA-table expansion, and publishes the reports in the job
summary and as artifacts.

To run locally, with internet access:

```bash
python -m scripts.references.ddinter --download --negatives 1000
```

```bash
python -m scripts.references.kegg
```

```bash
python -m scripts.references.pk_labels
```

```bash
python -m scripts.evaluate --reference eval/references/ddinter.csv --reference eval/references/kegg.csv --out eval/report.md
```

```bash
python -m scripts.evaluate_pk eval/references/pk_labels.csv --holdout-seed 7 --out eval/pk_report.md
```

## Still needed

A blinded pharmacist review (`docs/clinical_evaluation_protocol.md`) remains the strongest evidence. DDInter
is the scalable stand-in, since it was graded by pharmacists independently of this project, but it does not
replace a prospective panel.
