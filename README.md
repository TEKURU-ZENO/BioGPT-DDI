<h1 align="center">BioGPT-DDI</h1>

<p align="center">
  <b>Mechanism-aware, source-cited drug–drug interaction screening, with patient context, pharmacogenomics and grounded reports</b>
</p>

<p align="center">
  <i>Research prototype — not medical advice and not a substitute for a pharmacist or a licensed interaction database.</i>
</p>

---

## What makes it different

Most DDI tools either look up a pair in a database or predict a label with a black-box model. BioGPT-DDI combines
several layers, and every answer can be traced to a mechanism and a source:

| Layer | What it does |
|---|---|
| **Normalisation** | Brand names, salts, doses, RxNorm-style names (`warfarin sodium 5 MG Oral Tablet [Coumadin]`) and combination products are mapped to ingredients. Typos get suggestions and are never auto-corrected. |
| **Curated rules** | 40 interactions from product labelling and FDA Drug Safety Communications, each with mechanism, management, counselling and sources. |
| **Mechanism engine** | CYP3A4/2C9/2C19/2D6/1A2 and P-gp inhibition, induction and prodrug activation (FDA index-drug classes), plus pharmacodynamic axes: serotonin, QT, CNS depression, bleeding, potassium, RAAS, NSAID-renal, hypotension, bradycardia, hypoglycaemia, chelation. |
| **Quantitative PK** | A static mechanistic model estimates the change in exposure (e.g. "~5.3-fold AUC increase, range 2.8–10×"). |
| **Patient context** | eGFR-based renal dosing alerts and severity escalation, plus 2023 Beers Criteria for adults ≥ 65. |
| **Pharmacogenomics** | CPIC drug–gene guidance for CYP2D6, 2C19 and 2C9 with **phenoconversion**: a co-prescribed paroxetine turns a genetic normal CYP2D6 metaboliser into a functional poor one, so codeine is flagged. |
| **Regimen screen** | Every pair in a list of up to 15 drugs, plus cumulative burden: anticholinergic (ACB), QT, serotonergic, CNS-active (Beers), bleeding, potassium. |
| **External evidence** *(optional)* | DDInter severities fill gaps and flag disagreements; FDA label excerpts quote the passage that names the other drug. |
| **Learned signal** *(optional)* | A fingerprint model with drug-level cold-start evaluation and conformal prediction. It reports "predicted – not documented" signals only, and **never sets a severity**. |
| **Literature & pharmacovigilance** | Mines PubMed for emerging DDIs into a pharmacist review queue (pattern scorer or a BioGPT/BioBERT relation-extraction model) and screens FAERS for disproportionality signals. |
| **EHR integration** | A CDS Hooks 2.0 service (`order-sign`, `order-select`) returns interaction cards when orders are drafted. |

Severity is always decided by deterministic, cited layers. Language models are never used to decide or describe it.

### Result statuses

| Status | Severity | Meaning |
|---|---|---|
| `interaction_found` | Contraindicated / Major / Moderate / Minor | Findings with evidence level, sources and (for PK) an exposure estimate |
| `no_known_interaction` | None known | Both drugs are profiled and no interaction was found. **This is not a statement of safety.** |
| `unrecognized_drug` | Unknown | The input could not be identified; suggestions are returned |
| `insufficient_data` | Unknown | Recognised by RxNorm but not profiled in the knowledge base |

---

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/predict` | `{drug1, drug2, patient?}` → findings, patient alerts, reports |
| `POST /api/regimen` | `{drugs: [...], patient?}` → all pairs, burden scores, patient alerts, phenotypes |
| `POST /api/generate-pdf` | `{drug1, drug2, report_type: patient\|professional}` → PDF; the analysis is re-derived on the server |
| `GET /api/cds-services`, `POST /api/cds-services/biogpt-ddi` | CDS Hooks discovery and service |
| `GET /api/health` | Versions, knowledge-base size, and which optional layers are loaded |

`patient` is `{age?, egfr?, pgx?: {"CYP2D6": "PM"|"IM"|"NM"|"UM", "CYP2C19": ...+"RM", "CYP2C9": "PM"|"IM"|"NM"}}`.

```bash
curl -s localhost:8000/api/regimen -H 'content-type: application/json' -d '{
  "drugs": ["Codeine", "Paroxetine", "Clopidogrel", "Omeprazole", "Zolpidem"],
  "patient": {"age": 78, "pgx": {"CYP2D6": "NM", "CYP2C19": "IM"}}}'
```

That request returns:
- **Codeine:** the patient is a functional CYP2D6 poor metaboliser because paroxetine phenoconverts them, so codeine
  should be avoided.
- **Clopidogrel:** omeprazole converts the patient's genetic CYP2C19 IM status to a functional PM, so clopidogrel
  should be avoided.
- **Codeine + zolpidem:** Major, opioid with a CNS depressant.
- **Regimen:** three CNS-active drugs in an adult ≥ 65 (Beers), and an anticholinergic burden of 4.

---

## Repository layout

```
api/index.py                FastAPI app (Vercel serverless entry)
api/cds_hooks.py            CDS Hooks 2.0 service
api/ddi/lexicon.py          ~230 ingredient profiles + ~340 brand/synonym entries
api/ddi/normalize.py        name → ingredient resolution (local, optional RxNav)
api/ddi/rules.py            curated, source-attributed rules
api/ddi/engine.py           curated + mechanism + external + learned layers; pair and regimen analysis
api/ddi/pk_model.py         static mechanistic AUC-ratio estimates
api/ddi/patient.py          renal / Beers alerts and severity escalation
api/ddi/pgx.py              CPIC drug–gene rules and phenoconversion
api/ddi/burden.py           regimen burden scores (ACB, QT, serotonergic, CNS, bleeding, potassium)
api/ddi/evidence.py         optional DDInter + FDA label evidence
api/ddi/learned.py          optional learned-model signal
api/ddi/reports.py          grounded patient / professional text
api/utils/pdf_generator.py  PDF reports
scripts/                    import_ddinter, fetch_label_evidence (openFDA), evaluate
pipelines/                  literature (PubMed mining), faers (disproportionality)
research/ddi_ml/            learned layer: features, cold-start splits, conformal prediction, training CLI
eval/gold_standard.csv      regression gold set (shared by tests and scripts/evaluate.py)
docs/                       clinical evaluation protocol
src/                        React UI: Analyzer, Medication List, About
tests/                      250 tests
```

---

## Running locally

```bash
pip install -r api/requirements.txt -r requirements-dev.txt
```

```bash
uvicorn api.index:app --reload --port 8000
```

```bash
npm install && npm start
```

```bash
python -m pytest -q
```

```bash
python -m scripts.evaluate --out eval/report.md
```

Optional data and models:

```bash
python -m scripts.import_ddinter ddinter_downloads_code_*.csv
```

```bash
python -m scripts.fetch_label_evidence
```

```bash
pip install -r research/requirements.txt && python -m research.ddi_ml.train drugbank.csv --split cold_drug --names names.csv --out models/ddi_model.joblib
```

```bash
python -m pipelines.literature --days 30 --out review_queue.jsonl
```

```bash
python -m pipelines.faers warfarin fluconazole --reaction HAEMORRHAGE
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins (credentials are never allowed) |
| `DDI_ENABLE_RXNAV` | `true` | RxNorm lookup for names not in the lexicon |
| `DDI_DATA_DIR` | `api/ddi/data` | Location of the optional `external_ddi.json` / `label_evidence.json` |
| `DDI_MODEL_PATH` | — | Learned-model artifact (joblib; load only artifacts you built) |
| `BIOGPT_ENABLED`, `HF_API_TOKEN`, `BIOGPT_API_URL` | off | Experimental BioGPT literature context |
| `OPENFDA_API_KEY`, `NCBI_API_KEY` | — | Higher rate limits for the openFDA and PubMed pipelines |

Third-party data (DDInter, label excerpts) and model artifacts are git-ignored. Check each source's licence before
redistributing it. DDInter, for example, is free for non-commercial use only.

---

## Validation

- **Regression gold set:** 78 pairs in `eval/gold_standard.csv`. CI fails if safety-critical recall drops below
  100%. This set includes the cases version 1 got dangerously wrong:

  | Pair | v1 | now |
  |---|---|---|
  | Warfarin + Fluconazole | Minor | **Major** |
  | Linezolid + Sertraline | Minor | **Contraindicated** |
  | Tramadol + Sertraline | Minor | **Major** |
  | Clopidogrel + Omeprazole | Minor | **Major** |
  | Water + Sugar / "a" + "b" | Moderate / Major | **Unknown** |

- **The gold set is not clinical validation.** The developers assembled it. `docs/clinical_evaluation_protocol.md`
  describes the blinded pharmacist study needed before any claim of clinical usefulness. `scripts/evaluate.py
  --reference` computes its metrics (weighted kappa, under-call rate).
- **Learned layer:** the pipeline is tested on synthetic data with a known structural rule. **No trained model is
  shipped.** Real performance must be measured on DrugBank or TWOSIDES with cold-drug splits.

### Known limitations

- The knowledge base covers about 230 ingredients. Anything outside it is reported as unknown, never as safe.
- PK estimates are class-level, not drug-specific (no curated Ki or fm). Transporter effects are not quantified.
- Dose, hepatic function and VKORC1/HLA genotypes are not modelled.
- The CDS Hooks service does not verify the EHR's JWT. A deployment must add JWT verification and restrict CORS.
- Not clinically validated.

## Where BioGPT fits

[BioGPT](https://github.com/microsoft/BioGPT) is a PubMed-trained language model whose documented strength is
biomedical relation extraction. Here it has two roles. In the literature pipeline it can be the relation scorer
(`--scorer hf:<model>`) with any DDI-2013 fine-tuned checkpoint. In the API it can optionally add labelled,
unverified "literature context". It never decides or describes severity.

## License

MIT. Product names are trademarks of their respective owners and are used only for identification.

## Acknowledgements

- **BioGPT** by Microsoft Research
- U.S. FDA drug-interaction tables, Drug Safety Communications and openFDA; NLM RxNorm/RxNav and PubMed E-utilities
- CPIC and DPWG pharmacogenomic guidelines; American Geriatrics Society Beers Criteria; CredibleMeds; the ACB scale
- DDInter, Therapeutics Data Commons
