"""BioGPT-DDI API.

Severity comes from a deterministic, source-attributed engine (curated rules
+ mechanism rules). Language-model text is optional, labelled, and never
decides severity.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from api.cds_hooks import router as cds_router
from api.ddi import biogpt, evidence, learned
from api.ddi.engine import analyze_pair, analyze_regimen
from api.ddi.lexicon import DRUGS, GENERATED_ROLES, KB_VERSION
from api.ddi.patient import Patient
from api.ddi.pgx import VALID as PGX_VALID
from api.ddi.reports import attach_reports
from api.ddi.rules import CURATED
from api.utils.pdf_generator import DDIReportGenerator

logger = logging.getLogger("biogpt_ddi")
logging.basicConfig(level=logging.INFO)

API_VERSION = "2.0.0"
app = FastAPI(title="BioGPT-DDI API", version=API_VERSION)

_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,  # no cookies/auth are used; never combine credentials with "*"
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],  # CDS Hooks clients send a JWT bearer token
)
app.include_router(cds_router, prefix="/api")

pdf_generator = DDIReportGenerator()

_NAME_RE = re.compile(r"^[\w\s'’\-\.\(\)/+,%]+$", re.UNICODE)


def _validate_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("drug name is required")
    if not _NAME_RE.match(v):
        raise ValueError("drug name contains unsupported characters")
    return v


class PatientContext(BaseModel):
    age: Optional[float] = Field(None, ge=0, le=120)
    egfr: Optional[float] = Field(None, ge=0, le=200, description="eGFR in mL/min/1.73m2")
    pgx: Dict[str, str] = Field(default_factory=dict,
                                description="Genotype-derived phenotypes, e.g. {'CYP2D6': 'PM', 'CYP2C19': 'IM'}")

    @field_validator("pgx")
    @classmethod
    def _check_pgx(cls, v: Dict[str, str]) -> Dict[str, str]:
        out = {}
        for gene, pheno in v.items():
            gene, pheno = gene.upper().strip(), pheno.upper().strip()
            if gene not in PGX_VALID:
                raise ValueError(f"unsupported gene {gene!r}; supported: {sorted(PGX_VALID)}")
            if pheno not in PGX_VALID[gene]:
                raise ValueError(f"unsupported {gene} phenotype {pheno!r}; supported: {sorted(PGX_VALID[gene])}")
            out[gene] = pheno
        return out

    def to_patient(self) -> Patient:
        return Patient(age=self.age, egfr=self.egfr, pgx=dict(self.pgx))


class PredictionRequest(BaseModel):
    drug1: str = Field(..., min_length=1, max_length=100)
    drug2: str = Field(..., min_length=1, max_length=100)
    patient: Optional[PatientContext] = None

    @field_validator("drug1", "drug2")
    @classmethod
    def _check_names(cls, v: str) -> str:
        return _validate_name(v)


class RegimenRequest(BaseModel):
    drugs: List[str] = Field(..., min_length=2, max_length=15)
    patient: Optional[PatientContext] = None

    @field_validator("drugs")
    @classmethod
    def _check(cls, v: List[str]) -> List[str]:
        if any(len(d) > 100 for d in v):
            raise ValueError("drug name too long")
        return [_validate_name(d) for d in v]


class PDFRequest(BaseModel):
    drug1: str = Field(..., min_length=1, max_length=100)
    drug2: str = Field(..., min_length=1, max_length=100)
    report_type: Literal["patient", "professional"]
    # Accepted for backwards compatibility but ignored: the server re-derives
    # the analysis so a client cannot forge report content.
    prediction_data: Optional[dict] = None

    @field_validator("drug1", "drug2")
    @classmethod
    def _check_names(cls, v: str) -> str:
        return _validate_name(v)


def _run(drug1: str, drug2: str, patient: Optional[PatientContext] = None) -> dict:
    return attach_reports(analyze_pair(drug1, drug2, patient.to_patient() if patient else None))


@app.get("/")
@app.get("/api")
def read_root():
    return {"message": "BioGPT-DDI API is running", "status": "healthy", "version": API_VERSION}


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "version": API_VERSION,
        "knowledge_base": {"version": KB_VERSION, "ingredients": len(DRUGS), "curated_rules": len(CURATED),
                           "fda_cyp_roles": {k: (len(v) if isinstance(v, list) else v)
                                             for k, v in GENERATED_ROLES.items()}},
        "engine": "curated rules + mechanism rules (CYP/P-gp, pharmacodynamic axes)",
        "biogpt_literature_context": biogpt.enabled(),
        "external_evidence": evidence.external_status(),
        "learned_model": learned.status(),
    }


@app.post("/api/predict")
async def predict_interaction(request: PredictionRequest):
    try:
        result = _run(request.drug1, request.drug2, request.patient)
        result["literature_context"] = await biogpt.literature_context(result)
        if result["literature_context"]:
            result["literature_context_note"] = ("Experimental BioGPT continuation of the documented mechanism. "
                                                 "Unverified; not used for severity.")
        logger.info("predict %s + %s -> %s / %s", request.drug1, request.drug2, result["status"], result["severity"])
        return result
    except Exception:
        logger.exception("prediction failed")
        raise HTTPException(status_code=500, detail="Analysis failed due to an internal error. Please try again.") from None


@app.post("/api/regimen")
def check_regimen(request: RegimenRequest):
    try:
        patient = request.patient.to_patient() if request.patient else None
        return analyze_regimen(request.drugs, patient)
    except Exception:
        logger.exception("regimen check failed")
        raise HTTPException(status_code=500, detail="Regimen analysis failed due to an internal error.") from None


def _safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")[:40] or "drug"


@app.post("/api/generate-pdf")
def generate_pdf_report(request: PDFRequest):
    result = _run(request.drug1, request.drug2)
    try:
        if request.report_type == "patient":
            buffer = pdf_generator.generate_patient_report(result)
        else:
            buffer = pdf_generator.generate_professional_report(result)
    except Exception:
        logger.exception("pdf generation failed")
        raise HTTPException(status_code=500, detail="PDF generation failed due to an internal error.") from None

    filename = (f"DDI_Report_{request.report_type.title()}_"
                f"{_safe_filename(request.drug1)}_{_safe_filename(request.drug2)}.pdf")
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})
