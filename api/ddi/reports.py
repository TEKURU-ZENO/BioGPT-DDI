"""Evidence-grounded report text.

Reports are assembled only from engine findings, so every statement traces back
to a curated rule or a mechanism rule with a cited source. No free-running text
generation is used to decide or describe severity.
"""

from __future__ import annotations

from typing import List

SEVERITY_PATIENT = {
    "Contraindicated": "These medicines should NOT be taken together.",
    "Major": "This is a serious interaction. Talk to your doctor or pharmacist before taking these together.",
    "Moderate": "This interaction may need monitoring or a change in how you take your medicines.",
    "Minor": "This interaction is usually minor, but let your pharmacist know you take both.",
}


def _names(result: dict) -> tuple:
    return (result["drug1"].get("display_name") or result["drug1"]["input"],
            result["drug2"].get("display_name") or result["drug2"]["input"])


def patient_report(result: dict) -> str:
    a, b = _names(result)
    status = result["status"]
    if status == "unrecognized_drug":
        return (f"We could not identify one of the medicines you entered. {result['message']} "
                "Please check the name on the medicine's packaging, or ask your pharmacist.")
    if status == "insufficient_data":
        return (f"{result['message']} Please ask your pharmacist to check {a} and {b} together - they have access "
                "to complete interaction databases.")
    if status == "no_known_interaction":
        return (f"We did not find a known interaction between {a} and {b} in our database. Our database does not "
                "cover every medicine or every situation, so please still tell your doctor and pharmacist about "
                "all the medicines and supplements you take.")

    findings = result["findings"]
    parts: List[str] = [f"{a} and {b}: {SEVERITY_PATIENT.get(result['severity'], '')}"]
    for f in findings:
        parts.append(f["patient_summary"])
    watch = list(dict.fromkeys(w for f in findings for w in f["watch_for"]))
    if watch:
        parts.append("Get medical advice promptly if you notice: " + "; ".join(watch) + ".")
    parts.append("Do not stop or change any medicine on your own - speak to your doctor or pharmacist first. "
                 "If you have severe symptoms, seek emergency care.")
    return " ".join(p for p in parts if p)


def professional_report(result: dict) -> str:
    a, b = _names(result)
    status = result["status"]
    if status != "interaction_found":
        return f"{a} + {b}: {result['message']}"

    lines: List[str] = [
        f"{a} + {b}: overall severity {result['severity'].upper()} ({result['prediction']}). "
        f"Confidence: {result.get('confidence', 'n/a')}."
    ]
    for i, f in enumerate(result["findings"], 1):
        lines.append(
            f"[{i}] {f['title']} - {f['severity']} ({f['evidence_level']}). "
            f"Mechanism: {f['mechanism']} Clinical effect: {f['effect']} Management: {f['management']} "
            f"Sources: {'; '.join(f['evidence']) or 'n/a'}."
        )
    return "\n\n".join(lines)


def attach_reports(result: dict) -> dict:
    result["patient_report"] = patient_report(result)
    result["professional_report"] = professional_report(result)
    return result
