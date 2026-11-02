"""CDS Hooks 2.0 service for EHR integration (Phase 4).

Discovery:  GET  /api/cds-services
Service:    POST /api/cds-services/biogpt-ddi   (hooks: order-sign, order-select)

The EHR sends the draft MedicationRequests in ``context.draftOrders`` and, via
prefetch, the patient's active MedicationRequests, Patient resource and most
recent eGFR Observation. Each draft order is checked against the active
medications and the other drafts; one card per interacting pair is returned,
plus cards for patient-specific alerts (renal, age) on the drafted drugs.

This service never calls back to the EHR's FHIR server (no use of
``fhirServer``/``fhirAuthorization``): it works only from the request and
prefetch, which avoids server-side request forgery and keeps PHI exposure to
what the EHR chose to send. If prefetch is missing, only draft orders are
compared with each other, and an info card says so.

Spec: https://cds-hooks.hl7.org/2.0/
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.ddi.engine import SEVERITY_RANK, analyze_resolved
from api.ddi.normalize import ResolvedDrug, resolve
from api.ddi.patient import Patient, patient_alerts
from api.ddi.lexicon import DRUGS

router = APIRouter()

SERVICE_ID = "biogpt-ddi"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
EGFR_LOINC = {"62238-1", "98979-8", "48642-3", "48643-1", "33914-3", "69405-9", "77147-7"}
INDICATOR = {"Contraindicated": "critical", "Major": "critical", "Moderate": "warning", "Minor": "info"}
SOURCE = {"label": "BioGPT-DDI (research prototype - not for clinical use)", "topic": {
    "system": "https://github.com/TEKURU-ZENO/BioGPT-DDI", "code": "ddi", "display": "Drug-drug interaction"}}

DISCOVERY = {
    "services": [{
        "hook": hook,
        "id": SERVICE_ID if hook == "order-sign" else f"{SERVICE_ID}-select",
        "title": "BioGPT-DDI interaction check",
        "description": "Checks drafted medication orders against active medications for documented and "
                       "mechanism-based drug-drug interactions, with renal and age-related alerts.",
        "prefetch": {
            "patient": "Patient/{{context.patientId}}",
            "medications": "MedicationRequest?patient={{context.patientId}}&status=active",
            "egfr": "Observation?patient={{context.patientId}}&code=http://loinc.org|62238-1,"
                    "http://loinc.org|98979-8,http://loinc.org|48642-3&_sort=-date&_count=1",
        },
    } for hook in ("order-sign", "order-select")],
}


class HookRequest(BaseModel):
    hookInstance: str
    hook: str
    context: Dict[str, Any]
    prefetch: Optional[Dict[str, Any]] = None
    fhirServer: Optional[str] = None
    fhirAuthorization: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------- FHIR helpers

def _entries(bundle: Any) -> List[dict]:
    if not isinstance(bundle, dict):
        return []
    if bundle.get("resourceType") == "Bundle":
        return [e.get("resource") or {} for e in bundle.get("entry") or []]
    return [bundle]


def _med_name(mr: dict) -> Optional[str]:
    """Best human-readable medication name from a MedicationRequest."""
    cc = mr.get("medicationCodeableConcept") or (mr.get("medication") or {}).get("concept") or {}
    codings = cc.get("coding") or []
    rx = [c.get("display") for c in codings if c.get("system") == RXNORM and c.get("display")]
    other = [c.get("display") for c in codings if c.get("display")]
    if rx:
        return rx[0]
    return cc.get("text") or (other[0] if other else None)


def _medications(bundle: Any) -> List[Tuple[str, str]]:
    """[(name, MedicationRequest id)] for MedicationRequests in a bundle."""
    out = []
    for r in _entries(bundle):
        if r.get("resourceType") == "MedicationRequest":
            name = _med_name(r)
            if name:
                out.append((name, r.get("id", "")))
    return out


def _age(patient_res: Any) -> Optional[float]:
    if not isinstance(patient_res, dict) or not patient_res.get("birthDate"):
        return None
    try:
        y, m, d = (int(x) for x in (patient_res["birthDate"].split("-") + ["1", "1"])[:3])
        born, today = date(y, m, d), date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except ValueError:
        return None


def _egfr(bundle: Any) -> Optional[float]:
    for r in _entries(bundle):
        if r.get("resourceType") != "Observation":
            continue
        codes = {c.get("code") for c in (r.get("code") or {}).get("coding") or []}
        q = r.get("valueQuantity") or {}
        if codes & EGFR_LOINC and isinstance(q.get("value"), (int, float)):
            return float(q["value"])
    return None


# --------------------------------------------------------------------------- cards

def _pair_card(name_a: str, name_b: str, res: dict) -> dict:
    sev = res["severity"]
    top = res["findings"][0]
    detail = [f"**{sev}** - {top['title']}", "", f"**Mechanism:** {top['mechanism']}",
              f"**Clinical effect:** {top['effect']}", f"**Management:** {top['management']}"]
    if top.get("pk_estimate"):
        detail.append(f"**Estimated exposure change:** {top['pk_estimate']['summary']}")
    for note in top.get("patient_notes", []):
        detail.append(f"_{note}_")
    if len(res["findings"]) > 1:
        detail.append("")
        detail.append("Additional findings: " + "; ".join(f"{f['title']} ({f['severity']})" for f in res["findings"][1:]))
    if top["evidence"]:
        detail.append("")
        detail.append("Sources: " + "; ".join(top["evidence"]))
    summary = f"{sev} interaction: {name_a} + {name_b}"
    return {
        "uuid": str(uuid.uuid4()),
        "summary": summary[:140],
        "indicator": INDICATOR[sev],
        "detail": "\n".join(detail),
        "source": SOURCE,
        "overrideReasons": [
            {"code": "benefit-outweighs-risk", "system": "https://github.com/TEKURU-ZENO/BioGPT-DDI/override",
             "display": "Benefit outweighs risk"},
            {"code": "will-monitor", "system": "https://github.com/TEKURU-ZENO/BioGPT-DDI/override",
             "display": "Will monitor / adjust dose"},
        ],
    }


def _alert_card(a: dict) -> dict:
    return {"uuid": str(uuid.uuid4()), "summary": a["title"][:140],
            "indicator": {"critical": "critical", "warning": "warning"}.get(a["level"], "info"),
            "detail": f"{a['message']}\n\nSource: {a['source']}", "source": SOURCE}


@router.get("/cds-services")
def discovery():
    return DISCOVERY


@router.post("/cds-services/{service_id}")
def run_service(service_id: str, req: HookRequest):
    if service_id not in (SERVICE_ID, f"{SERVICE_ID}-select"):
        raise HTTPException(status_code=404, detail="unknown service")
    drafts = _medications(req.context.get("draftOrders"))
    if not drafts:
        return {"cards": []}
    prefetch = req.prefetch or {}
    active = _medications(prefetch.get("medications"))
    patient = Patient(age=_age(prefetch.get("patient")), egfr=_egfr(prefetch.get("egfr")))

    resolved: Dict[str, ResolvedDrug] = {n: resolve(n) for n, _ in drafts + active}
    cards: List[dict] = []
    seen = set()
    draft_names = [n for n, _ in drafts]
    for i, d in enumerate(draft_names):
        others = [n for n, _ in active] + draft_names[i + 1:]
        for o in others:
            key = tuple(sorted((d.lower(), o.lower())))
            if key in seen or key[0] == key[1]:
                continue
            seen.add(key)
            res = analyze_resolved(resolved[d], resolved[o], patient if not patient.empty else None)
            if res["status"] == "interaction_found":
                cards.append((SEVERITY_RANK[res["severity"]], _pair_card(d, o, res)))

    draft_profiles = [DRUGS[i] for n in draft_names if resolved[n].recognized for i in resolved[n].ingredients]
    if not patient.empty and draft_profiles:
        for a in patient_alerts(draft_profiles, patient)["alerts"]:
            if a["category"] in ("renal", "age") and a["level"] != "info":
                cards.append((2 if a["level"] == "critical" else 1, _alert_card(a)))

    out = [c for _, c in sorted(cards, key=lambda x: -x[0])]
    unrecognized = sorted({n for n in draft_names if not resolved[n].recognized})
    if unrecognized:
        out.append({"uuid": str(uuid.uuid4()), "indicator": "info", "source": SOURCE,
                    "summary": f"Not checked (unrecognised): {', '.join(unrecognized)}"[:140]})
    if not prefetch.get("medications"):
        out.append({"uuid": str(uuid.uuid4()), "indicator": "info", "source": SOURCE,
                    "summary": "Active medications were not provided; only drafted orders were compared."})
    return {"cards": out}
