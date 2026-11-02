"""PDF reports built only from the server-side analysis result.

All dynamic text is XML-escaped before it reaches ReportLab, whose Paragraph
parses a mini-markup language.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable, List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SEVERITY_COLORS = {
    "Contraindicated": "#7f1d1d",
    "Major": "#b91c1c",
    "Moderate": "#b45309",
    "Minor": "#15803d",
    "None known": "#374151",
    "Unknown": "#374151",
}


def _e(text) -> str:
    return escape(str(text if text is not None else ""))


class DDIReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        add = self.styles.add
        add(ParagraphStyle("DDITitle", parent=self.styles["Heading1"], fontSize=20, alignment=TA_CENTER,
                           textColor=colors.HexColor("#4c1d95"), spaceAfter=16))
        add(ParagraphStyle("DDISection", parent=self.styles["Heading2"], fontSize=14,
                           textColor=colors.HexColor("#4c1d95"), spaceBefore=12, spaceAfter=6))
        add(ParagraphStyle("DDISub", parent=self.styles["Heading3"], fontSize=11.5, spaceBefore=8, spaceAfter=4))
        add(ParagraphStyle("DDIBody", parent=self.styles["BodyText"], fontSize=10.5, leading=15,
                           alignment=TA_LEFT, spaceAfter=6))
        add(ParagraphStyle("DDISmall", parent=self.styles["BodyText"], fontSize=8.5, leading=11,
                           textColor=colors.HexColor("#4b5563")))

    # ------------------------------------------------------------------ helpers
    def _p(self, text: str, style: str = "DDIBody") -> Paragraph:
        return Paragraph(text, self.styles[style])

    def _names(self, r: dict):
        return (r["drug1"].get("display_name") or r["drug1"]["input"],
                r["drug2"].get("display_name") or r["drug2"]["input"])

    def _meta_table(self, rows: List[List[str]]) -> Table:
        data = [[self._p(f"<b>{_e(k)}</b>"), self._p(_e(v))] for k, v in rows]
        t = Table(data, colWidths=[1.9 * inch, 4.9 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return t

    def _severity_banner(self, severity: str) -> Table:
        color = colors.HexColor(SEVERITY_COLORS.get(severity, "#374151"))
        t = Table([[self._p(f"<font color='white'><b>Overall severity: {_e(severity)}</b></font>")]],
                  colWidths=[6.8 * inch])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        return t

    def _bullets(self, items: Iterable[str]) -> List[Paragraph]:
        return [self._p(f"&bull; {_e(i)}") for i in items]

    def _footer(self, r: dict) -> List:
        return [
            Spacer(1, 0.25 * inch),
            self._p("Disclaimer", "DDISection"),
            self._p(_e(r["disclaimer"])),
            self._p(f"Knowledge base version {_e(r['kb_version'])}. Generated "
                    f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by BioGPT-DDI "
                    "(curated rules + mechanism engine).", "DDISmall"),
        ]

    def _build(self, story: List) -> BytesIO:
        buffer = BytesIO()
        SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                          leftMargin=0.85 * inch, rightMargin=0.85 * inch).build(story)
        buffer.seek(0)
        return buffer

    # ------------------------------------------------------------------ patient
    def generate_patient_report(self, r: dict) -> BytesIO:
        a, b = self._names(r)
        story: List = [self._p(f"Medicine Interaction Report<br/>{_e(a)} and {_e(b)}", "DDITitle"),
                       self._severity_banner(r["severity"]), Spacer(1, 0.15 * inch)]

        story.append(self._p("What this means for you", "DDISection"))
        story.append(self._p(_e(r["patient_report"])))

        findings = r.get("findings") or []
        watch = list(dict.fromkeys(w for f in findings for w in f["watch_for"]))
        if watch:
            story.append(self._p("Warning signs to look out for", "DDISection"))
            story.extend(self._bullets(watch))

        story.append(self._p("What you should do", "DDISection"))
        story.extend(self._bullets([
            "Do not stop or change any medicine without speaking to your doctor or pharmacist.",
            "Show this report to your doctor or pharmacist and tell them about every medicine, supplement and "
            "herbal product you take.",
            "If you have severe symptoms (such as trouble breathing, chest pain, fainting or heavy bleeding), "
            "call emergency services.",
        ]))
        story.append(self._p("Questions to ask your doctor or pharmacist", "DDISection"))
        story.extend(self._bullets([
            "Is it safe for me to take these medicines together?",
            "Should the dose or timing of either medicine change?",
            "Is there an alternative medicine that does not interact?",
            "Do I need any blood tests or other monitoring?",
        ]))
        story.extend(self._footer(r))
        return self._build(story)

    # ------------------------------------------------------------------ professional
    def generate_professional_report(self, r: dict) -> BytesIO:
        a, b = self._names(r)
        story: List = [self._p(f"Clinical Drug-Drug Interaction Report<br/>{_e(a)} + {_e(b)}", "DDITitle"),
                       self._severity_banner(r["severity"]), Spacer(1, 0.15 * inch)]

        def drug_row(d: dict) -> str:
            ing = ", ".join(i.title() for i in d.get("ingredients") or []) or "-"
            return f"{d['input']}  ->  {ing}  (matched via {d.get('matched_via', 'none')})"

        story.append(self._meta_table([
            ["Drug 1", drug_row(r["drug1"])],
            ["Drug 2", drug_row(r["drug2"])],
            ["Status", r["status"].replace("_", " ")],
            ["Classification", r.get("prediction", "-")],
            ["Confidence", r.get("confidence", "-")],
        ]))

        findings = r.get("findings") or []
        if not findings:
            story.append(self._p("Result", "DDISection"))
            story.append(self._p(_e(r.get("message", ""))))
        for i, f in enumerate(findings, 1):
            block = [
                self._p(f"{i}. {_e(f['title'])}", "DDISection"),
                self._meta_table([["Severity", f["severity"]], ["Category", f["category"]],
                                  ["Evidence level", f["evidence_level"]]]),
                self._p("Mechanism", "DDISub"), self._p(_e(f["mechanism"])),
                self._p("Clinical effect", "DDISub"), self._p(_e(f["effect"])),
            ]
            if f.get("pk_estimate"):
                block += [self._p("Estimated exposure change", "DDISub"),
                          self._p(_e(f["pk_estimate"]["summary"])),
                          self._p(_e(f["pk_estimate"]["assumptions"]), "DDISmall")]
            block += [
                self._p("Management", "DDISub"), self._p(_e(f["management"])),
            ]
            if f["watch_for"]:
                block += [self._p("Counsel the patient to report", "DDISub")] + self._bullets(f["watch_for"])
            if f["evidence"]:
                block += [self._p("Sources", "DDISub")] + [self._p(_e(s), "DDISmall") for s in f["evidence"]]
            story.append(KeepTogether(block[:4]))
            story.extend(block[4:])

        story.append(self._p("Methodology and limitations", "DDISection"))
        story.append(self._p(
            "Severity is assigned deterministically: curated rules derived from product labeling and regulatory "
            "communications take precedence; otherwise a mechanism engine infers interactions from CYP450 / "
            "P-glycoprotein roles (FDA index-drug classification) and pharmacodynamic risk axes (serotonergic, "
            "QT, CNS depression, bleeding, potassium, RAAS, haemodynamic). Exposure changes are class-level static-"
            "model estimates. Patient context (renal function, age, pharmacogenomics) is available via the "
            "Medication List screen and API but is not included in this report; dose and hepatic function are not "
            "modelled. This report has not been "
            "validated for clinical use and must be checked against a licensed interaction database."))
        story.extend(self._footer(r))
        return self._build(story)
