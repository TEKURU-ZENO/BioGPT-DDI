<h1 align="center">BioGPT-DDI</h1>

<p align="center">
  <b>Mechanism-aware, source-cited drug–drug interaction screening with grounded patient and professional reports</b>
</p>

<p align="center">
  <i>Research prototype — not medical advice and not a substitute for a pharmacist or a licensed interaction database.</i>
</p>

---

## What it does

Given two medicines (generic names, brand names, salts, doses or combination products), BioGPT-DDI:

1. **Normalises** the input to active ingredients: `Coumadin` → warfarin, `Percocet` → oxycodone + acetaminophen,
   `Metoprolol tartrate 50 mg` → metoprolol. Optionally, names that aren't in the local lexicon are looked up in NLM RxNorm.
   Typos are **never** auto-corrected; the user gets "did you mean…" suggestions instead.
2. **Checks curated rules** taken from product labelling and FDA Drug Safety Communications. Each rule carries the
   mechanism, clinical effect, management and sources.
3. **Runs a mechanism engine** for pairs with no curated rule:
   - **Pharmacokinetic:** CYP3A4, 2C9, 2C19, 2D6 and 1A2, plus P-gp inhibition and induction graded by the FDA
     index-drug classification (strong/moderate/weak × sensitive/moderate substrate, with narrow-therapeutic-index
     escalation) and prodrug activation loss.
   - **Pharmacodynamic:** serotonin toxicity (MAOI → contraindicated), QT/TdP, opioid and CNS depression, bleeding,
     hyperkalaemia, dual RAAS blockade, NSAID nephrotoxicity, hypotension, bradycardia/AV block, hypoglycaemia with
     alcohol, chelation.
4. **Builds reports only from those findings**, so the explanation can never contradict the severity.

Every result has an explicit status:

| Status | Severity | Meaning |
|---|---|---|
| `interaction_found` | Contraindicated / Major / Moderate / Minor | One or more findings, each with an evidence level and sources |
| `no_known_interaction` | None known | Both drugs are profiled and no interaction was found. **This does not mean the combination is safe.** |
| `unrecognized_drug` | Unknown | Input could not be identified; suggestions are returned |
| `insufficient_data` | Unknown | Recognised by RxNorm but not profiled in the knowledge base |

### Example

```bash
curl -s localhost:8000/api/predict -H 'content-type: application/json' \
  -d '{"drug1":"Coumadin","drug2":"Diflucan"}'
```

The result is **Major**, pharmacokinetic. Fluconazole inhibits CYP2C9, which clears S-warfarin, so INR and bleeding risk
rise. Management: avoid the combination or check INR within 3–5 days and reduce the warfarin dose. Sources: the warfarin
prescribing information and the FDA CYP table.

---

## Architecture

```
src/                     React UI (analyzer, patient/professional tabs, PDF download)
api/index.py             FastAPI app: /api/predict, /api/regimen, /api/generate-pdf, /api/health
api/ddi/lexicon.py       ~230 ingredient profiles (classes, PD flags, CYP/P-gp roles, NTI) + ~340 brand/synonym entries
api/ddi/normalize.py     name → ingredient resolution (local first, optional RxNav fallback)
api/ddi/rules.py         curated, source-attributed rules
api/ddi/engine.py        curated + mechanism engine, severity aggregation, regimen (polypharmacy) screen
api/ddi/reports.py       grounded patient / professional text
api/ddi/biogpt.py        optional, labelled BioGPT literature-style context (off by default)
api/utils/pdf_generator.py  PDF reports (server re-derives the analysis; input is escaped)
tests/                   clinical regression gold set, KB integrity, normalisation, API and PDF tests
```

### Where BioGPT fits

[BioGPT](https://github.com/microsoft/BioGPT) is a PubMed-trained generative model. It is not instruction-tuned, and
when generating free text it can invent pharmacology. **It never decides or describes severity here.** If enabled
(`BIOGPT_ENABLED=true` and `HF_API_TOKEN`), it continues the already-documented mechanism, and the output is returned
separately as `literature_context` with an "unverified" label. Its documented strength is biomedical relation
extraction, which the roadmap below uses for literature mining.

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

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins (credentials are never allowed) |
| `DDI_ENABLE_RXNAV` | `true` | RxNorm lookup for names not in the local lexicon |
| `BIOGPT_ENABLED` | `false` | Enable the experimental BioGPT literature context |
| `HF_API_TOKEN` | — | Hugging Face token (only used if BioGPT is enabled) |
| `BIOGPT_API_URL` | HF router URL for `microsoft/BioGPT-Large` | Override the inference endpoint |

---

## Validation

`tests/test_clinical_regression.py` holds a gold set of documented interactions with their **minimum** expected
severity, plus non-interacting pairs and nonsense inputs. CI runs it on every push. It includes the cases that
version 1 got dangerously wrong:

| Pair | v1 | v2 |
|---|---|---|
| Warfarin + Fluconazole | Minor | **Major** |
| Linezolid + Sertraline | Minor | **Contraindicated** |
| Tramadol + Sertraline | Minor | **Major** |
| Clopidogrel + Omeprazole | Minor | **Major** |
| Coumadin + Aspirin | Minor | **Major** |
| Water + Sugar | Moderate | **Unknown** (unrecognised) |
| "a" + "b" | Major | **Unknown** (unrecognised) |

### Known limitations
- The knowledge base covers about 230 common ingredients. Anything outside it is reported as unknown or "insufficient
  data", never as safe.
- Dose, renal and hepatic function, age and pharmacogenomics are not yet modelled.
- Not clinically validated. Severity grading follows labelling where it exists, but can differ from commercial
  compendia.

---

## Roadmap

- **Phase 1 – evidence layer:** ingest DDInter and DailyMed SPL Section 7; per-claim citations with links; a
  polypharmacy UI on top of `/api/regimen`, with cumulative burden scores (QT, serotonergic, anticholinergic, CNS).
- **Phase 2 – quantitative PK and patient context:** static mechanistic AUC-ratio prediction; eGFR and Child-Pugh
  adjustments; CPIC-based drug–drug–gene interactions, including phenoconversion.
- **Phase 3 – learned layer:** a graph/molecular model for pairs not in the knowledge base, evaluated on drug-level
  cold-start splits with conformal prediction. Its output is labelled "predicted – not documented" and may only
  *raise* concern.
- **Phase 4 – living knowledge:** BioGPT relation extraction over new PubMed abstracts plus FAERS disproportionality
  signals, feeding a pharmacist review queue; clinician evaluation study; FHIR / CDS Hooks interface.

---

## License

MIT. Product names are trademarks of their respective owners and are used only for identification.

## Acknowledgements

- **BioGPT** by Microsoft Research
- U.S. FDA drug-interaction tables and Drug Safety Communications; NLM RxNorm / RxNav
- CredibleMeds (QT risk classification), CPIC / PharmGKB (planned)
