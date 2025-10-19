from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors
from datetime import datetime
from io import BytesIO

class DDIReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Create custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Section heading
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#764ba2'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))
        
        # Subsection heading
        self.styles.add(ParagraphStyle(
            name='SubsectionHeading',
            parent=self.styles['Heading3'],
            fontSize=13,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        ))
        
        # Body text
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
            leading=16
        ))
        
        # Warning text
        self.styles.add(ParagraphStyle(
            name='WarningText',
            parent=self.styles['BodyText'],
            fontSize=11,
            textColor=colors.red,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
            leading=16,
            fontName='Helvetica-Bold'
        ))
    
    def generate_patient_report(self, drug1: str, drug2: str, prediction: dict) -> BytesIO:
        """Generate detailed patient-friendly PDF report"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Title
        title = Paragraph(f"Drug Interaction Report<br/>{drug1} and {drug2}", self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 0.3*inch))
        
        # Report metadata
        date_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        meta_data = [
            ['Report Type:', 'Patient Summary'],
            ['Generated:', date_str],
            ['Interaction Type:', prediction.get('prediction', 'Unknown')],
            ['Severity Level:', prediction.get('severity', 'Unknown')]
        ]
        
        meta_table = Table(meta_data, colWidths=[2*inch, 4*inch])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Warning box
        if prediction.get('severity', '').lower() in ['major', 'moderate']:
            warning = Paragraph(
                "⚠️ IMPORTANT: This report is for informational purposes only. "
                "Always consult with your healthcare provider before making any changes to your medications.",
                self.styles['WarningText']
            )
            story.append(warning)
            story.append(Spacer(1, 0.2*inch))
        
        # Section 1: What This Means for You
        story.append(Paragraph("What This Means for You", self.styles['SectionHeading']))
        story.append(Paragraph(
            f"When you take {drug1} and {drug2} together, they may interact with each other in your body. "
            f"This interaction has been classified as <b>{prediction.get('severity', 'Unknown')}</b> severity, "
            f"which means it requires attention and possibly adjustments to your treatment plan.",
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.15*inch))
        
        # Section 2: Understanding the Interaction
        story.append(Paragraph("Understanding the Interaction", self.styles['SectionHeading']))
        story.append(Paragraph(
            prediction.get('patient_report', 'No detailed information available.'),
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.15*inch))
        
        # Section 3: How These Drugs Might Affect Each Other
        story.append(Paragraph("How These Drugs Might Affect Each Other", self.styles['SectionHeading']))
        
        story.append(Paragraph("Possible Effects:", self.styles['SubsectionHeading']))
        effects_text = f"""
        When {drug1} and {drug2} are taken together, several things might happen:
        <br/><br/>
        • <b>Changes in Drug Levels:</b> One drug might increase or decrease how much of the other drug 
        stays in your bloodstream. This could make one drug stronger or weaker than expected.
        <br/><br/>
        • <b>Combined Effects:</b> Both drugs might work on similar parts of your body, which could 
        strengthen their effects (sometimes too much) or work against each other.
        <br/><br/>
        • <b>Side Effects:</b> The combination might increase the chance of experiencing side effects 
        from either medication.
        <br/><br/>
        • <b>Timing Matters:</b> Taking these medications at different times of day might help reduce 
        the interaction, but only your doctor can advise on this.
        """
        story.append(Paragraph(effects_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.15*inch))
        
        # Section 4: What You Should Watch For
        story.append(Paragraph("What You Should Watch For", self.styles['SectionHeading']))
        
        symptoms_text = """
        While taking these medications together, pay attention to:
        <br/><br/>
        • <b>New or Unusual Symptoms:</b> Any symptoms you haven't experienced before, such as dizziness, 
        nausea, unusual tiredness, or changes in how you feel.
        <br/><br/>
        • <b>Changes in Existing Conditions:</b> If you notice your condition isn't improving as expected 
        or seems to be getting worse.
        <br/><br/>
        • <b>Side Effects:</b> Increased frequency or severity of side effects you may already experience 
        from either medication.
        <br/><br/>
        • <b>Allergic Reactions:</b> Skin rashes, itching, swelling, or difficulty breathing (seek 
        immediate medical attention if these occur).
        """
        story.append(Paragraph(symptoms_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.15*inch))
        
        # Section 5: What You Should Do
        story.append(Paragraph("What You Should Do", self.styles['SectionHeading']))
        
        actions_text = """
        <b>1. Talk to Your Healthcare Provider:</b>
        <br/>
        Schedule an appointment with your doctor or pharmacist to discuss this interaction. Bring this 
        report with you. They can:
        <br/>
        • Adjust the doses of your medications
        <br/>
        • Change the timing of when you take each medication
        <br/>
        • Prescribe alternative medications if needed
        <br/>
        • Order additional monitoring or tests
        <br/><br/>
        
        <b>2. Don't Stop Taking Your Medications:</b>
        <br/>
        Unless your doctor tells you to stop, continue taking both medications as prescribed. Suddenly 
        stopping medications can be dangerous.
        <br/><br/>
        
        <b>3. Keep a Symptom Diary:</b>
        <br/>
        Write down any new symptoms, when they occur, and how severe they are. This information will 
        help your healthcare provider make the best decisions about your treatment.
        <br/><br/>
        
        <b>4. Inform All Your Healthcare Providers:</b>
        <br/>
        Make sure all your doctors, dentists, and pharmacists know about all the medications you're taking, 
        including over-the-counter drugs and supplements.
        <br/><br/>
        
        <b>5. Be Consistent:</b>
        <br/>
        Take your medications at the same times each day unless instructed otherwise. Consistency helps 
        your body maintain stable drug levels.
        """
        story.append(Paragraph(actions_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 6: Questions to Ask Your Doctor
        story.append(Paragraph("Questions to Ask Your Doctor", self.styles['SectionHeading']))
        
        questions_text = """
        Consider asking your healthcare provider:
        <br/><br/>
        • Is it safe for me to continue taking both medications?
        <br/>
        • Do I need to adjust the doses or timing?
        <br/>
        • Are there alternative medications that don't interact?
        <br/>
        • What symptoms should I watch for specifically?
        <br/>
        • Do I need any special monitoring or blood tests?
        <br/>
        • Should I take these medications with or without food?
        <br/>
        • Are there any foods, beverages, or supplements I should avoid?
        <br/>
        • What should I do if I experience side effects?
        """
        story.append(Paragraph(questions_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Footer
        story.append(PageBreak())
        story.append(Paragraph("Important Disclaimers", self.styles['SectionHeading']))
        disclaimer_text = """
        <b>Medical Disclaimer:</b> This report is generated by an AI system for informational and 
        educational purposes only. It is not a substitute for professional medical advice, diagnosis, 
        or treatment. Always seek the advice of your physician or other qualified health provider with 
        any questions you may have regarding your medications or medical condition.
        <br/><br/>
        <b>Accuracy:</b> While this system uses advanced AI models trained on biomedical literature, 
        drug interactions are complex and may vary based on individual factors such as age, weight, 
        other medications, medical conditions, and genetics. Only your healthcare provider can provide 
        personalized advice for your specific situation.
        <br/><br/>
        <b>Emergency:</b> If you experience severe symptoms, difficulty breathing, chest pain, or other 
        signs of a serious reaction, seek emergency medical attention immediately by calling your local 
        emergency number or going to the nearest emergency room.
        <br/><br/>
        <b>Report Generated by:</b> BioGPT-DI - AI-Powered Drug Interaction Analysis System
        <br/>
        <b>Technology:</b> Fine-tuned BioBERT for classification, BioGPT for report generation
        <br/>
        <b>Generated:</b> {date}
        """.format(date=date_str)
        story.append(Paragraph(disclaimer_text, self.styles['BodyText']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_professional_report(self, drug1: str, drug2: str, prediction: dict) -> BytesIO:
        """Generate detailed professional/clinical PDF report"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Title
        title = Paragraph(
            f"Clinical Drug-Drug Interaction Report<br/>{drug1} – {drug2}",
            self.styles['CustomTitle']
        )
        story.append(title)
        story.append(Spacer(1, 0.3*inch))
        
        # Report metadata
        date_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        meta_data = [
            ['Report Type:', 'Professional/Clinical Summary'],
            ['Generated:', date_str],
            ['Interaction Classification:', prediction.get('prediction', 'Unknown')],
            ['Severity Assessment:', prediction.get('severity', 'Unknown')],
            ['Analysis Method:', 'Fine-tuned BioBERT + BioGPT']
        ]
        
        meta_table = Table(meta_data, colWidths=[2.5*inch, 3.5*inch])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['SectionHeading']))
        story.append(Paragraph(
            f"This report presents an AI-generated analysis of the potential drug-drug interaction between "
            f"<b>{drug1}</b> and <b>{drug2}</b>. The interaction has been classified as "
            f"<b>{prediction.get('prediction', 'UNKNOWN')}</b> with a severity level of "
            f"<b>{prediction.get('severity', 'UNKNOWN')}</b>. Clinical vigilance and appropriate "
            f"monitoring strategies are recommended.",
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 1: Interaction Overview
        story.append(Paragraph("1. Interaction Overview and Classification", self.styles['SectionHeading']))
        
        story.append(Paragraph("1.1 Interaction Type", self.styles['SubsectionHeading']))
        interaction_types = {
            'EFFECT': 'The interaction results in a modification of the therapeutic or adverse effects of one or both drugs.',
            'MECHANISM': 'The interaction occurs through a specific pharmacological mechanism (e.g., enzyme inhibition, receptor competition).',
            'ADVICE': 'Clinical guidance or recommendation regarding the concurrent use of these agents.',
            'INT': 'General interaction detected without specific classification.'
        }
        story.append(Paragraph(
            f"<b>Classification:</b> {prediction.get('prediction', 'UNKNOWN')}",
            self.styles['CustomBody']
        ))
        story.append(Paragraph(
            interaction_types.get(prediction.get('prediction', ''), 'Interaction type not specified.'),
            self.styles['CustomBody']
        ))
        
        story.append(Paragraph("1.2 Clinical Significance", self.styles['SubsectionHeading']))
        story.append(Paragraph(
            prediction.get('professional_report', 'Detailed clinical information not available.'),
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 2: Pharmacological Mechanism
        story.append(Paragraph("2. Pharmacological Mechanism", self.styles['SectionHeading']))
        
        story.append(Paragraph("2.1 Pharmacokinetic Interactions", self.styles['SubsectionHeading']))
        pk_text = f"""
        The interaction between {drug1} and {drug2} may involve one or more pharmacokinetic processes:
        <br/><br/>
        <b>Absorption:</b> One drug may alter the absorption of the other through changes in gastric pH, 
        gastrointestinal motility, or by forming complexes that affect bioavailability. This can result 
        in decreased therapeutic efficacy or increased risk of subtherapeutic dosing.
        <br/><br/>
        <b>Distribution:</b> Competition for plasma protein binding sites may increase the free (unbound) 
        fraction of one or both drugs, potentially leading to enhanced pharmacological effects or toxicity, 
        particularly for drugs with narrow therapeutic indices.
        <br/><br/>
        <b>Metabolism:</b> The most common mechanism of drug-drug interactions. One drug may:
        <br/>
        • <i>Inhibit</i> metabolic enzymes (primarily CYP450 isoenzymes), leading to increased plasma 
        concentrations of the substrate drug and potential toxicity
        <br/>
        • <i>Induce</i> metabolic enzymes, leading to increased metabolism and decreased plasma 
        concentrations of the substrate drug, potentially resulting in therapeutic failure
        <br/><br/>
        <b>Excretion:</b> Interactions may occur at the level of renal tubular secretion or reabsorption, 
        particularly involving drugs that are substrates for transport proteins such as P-glycoprotein or 
        organic anion/cation transporters.
        """
        story.append(Paragraph(pk_text, self.styles['CustomBody']))
        
        story.append(Paragraph("2.2 Pharmacodynamic Interactions", self.styles['SubsectionHeading']))
        pd_text = f"""
        Pharmacodynamic interactions occur when {drug1} and {drug2} have:
        <br/><br/>
        <b>Synergistic Effects:</b> Both drugs may act on the same or similar receptors, or affect the 
        same physiological system, resulting in an additive or potentiated response. This may be 
        therapeutically beneficial or may increase the risk of adverse effects.
        <br/><br/>
        <b>Antagonistic Effects:</b> The drugs may have opposing effects on the same physiological 
        system, potentially reducing the therapeutic efficacy of one or both agents.
        <br/><br/>
        <b>Enhanced Toxicity:</b> The combination may increase the risk of specific adverse effects 
        through cumulative toxicity on organ systems (e.g., nephrotoxicity, hepatotoxicity, 
        cardiotoxicity, or hematological effects).
        """
        story.append(Paragraph(pd_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 3: Clinical Manifestations
        story.append(Paragraph("3. Clinical Manifestations and Monitoring", self.styles['SectionHeading']))
        
        story.append(Paragraph("3.1 Potential Clinical Outcomes", self.styles['SubsectionHeading']))
        outcomes_text = f"""
        The concurrent administration of {drug1} and {drug2} may result in:
        <br/><br/>
        • <b>Therapeutic Failure:</b> Reduced efficacy of one or both drugs due to decreased plasma 
        concentrations or antagonistic effects
        <br/><br/>
        • <b>Dose-Related Toxicity:</b> Increased adverse effects due to elevated plasma concentrations 
        or synergistic toxicity
        <br/><br/>
        • <b>Delayed or Accelerated Onset of Action:</b> Altered pharmacokinetics may change the time 
        to reach therapeutic levels
        <br/><br/>
        • <b>Prolonged Effects:</b> Extended duration of drug action due to delayed elimination
        <br/><br/>
        • <b>Organ-Specific Toxicity:</b> Cumulative effects on specific organ systems requiring 
        targeted monitoring
        """
        story.append(Paragraph(outcomes_text, self.styles['CustomBody']))
        
        story.append(Paragraph("3.2 Recommended Monitoring Parameters", self.styles['SubsectionHeading']))
        monitoring_text = """
        <b>Clinical Monitoring:</b>
        <br/>
        • Baseline assessment of relevant organ function before initiating therapy
        <br/>
        • Regular evaluation of therapeutic response and emergence of adverse effects
        <br/>
        • Patient education regarding signs and symptoms requiring immediate medical attention
        <br/><br/>
        
        <b>Laboratory Monitoring:</b>
        <br/>
        • Therapeutic drug monitoring (TDM) where applicable
        <br/>
        • Organ function tests (hepatic, renal, cardiac as indicated)
        <br/>
        • Hematological parameters if bone marrow suppression is a concern
        <br/>
        • Electrolyte panels for drugs affecting fluid and electrolyte balance
        <br/><br/>
        
        <b>Frequency:</b> Monitoring frequency should be individualized based on:
        <br/>
        • Severity of the interaction
        <br/>
        • Patient-specific risk factors (age, comorbidities, renal/hepatic function)
        <br/>
        • Therapeutic index of the drugs involved
        <br/>
        • Initial response to therapy
        """
        story.append(Paragraph(monitoring_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 4: Clinical Management
        story.append(Paragraph("4. Clinical Management Strategies", self.styles['SectionHeading']))
        
        story.append(Paragraph("4.1 Risk Stratification", self.styles['SubsectionHeading']))
        risk_text = f"""
        <b>Severity: {prediction.get('severity', 'Unknown')}</b>
        <br/><br/>
        • <b>Major:</b> May be life-threatening and/or require medical intervention to prevent serious 
        outcomes. Combination usually contraindicated or requires intensive monitoring.
        <br/><br/>
        • <b>Moderate:</b> May result in exacerbation of condition and/or require alteration in therapy. 
        Combination should be used with caution and appropriate monitoring.
        <br/><br/>
        • <b>Minor:</b> Limited clinical significance. May increase monitoring or require minor 
        adjustments in therapy.
        """
        story.append(Paragraph(risk_text, self.styles['CustomBody']))
        
        story.append(Paragraph("4.2 Management Recommendations", self.styles['SubsectionHeading']))
        management_text = f"""
        <b>Dose Adjustment:</b>
        <br/>
        Consider empiric dose reduction of 25-50% for the affected drug(s), with subsequent titration 
        based on clinical response and therapeutic drug monitoring when available.
        <br/><br/>
        
        <b>Temporal Separation:</b>
        <br/>
        If the interaction is related to absorption, administering the drugs at different times 
        (typically 2-4 hours apart) may mitigate the interaction. This strategy is less effective 
        for metabolic interactions.
        <br/><br/>
        
        <b>Alternative Therapy:</b>
        <br/>
        Consider selecting alternative agents with similar therapeutic effects but without significant 
        interaction potential. Consult current formulary and evidence-based guidelines for appropriate 
        substitutions.
        <br/><br/>
        
        <b>Enhanced Monitoring:</b>
        <br/>
        If continuation of both drugs is clinically necessary:
        <br/>
        • Implement intensive clinical and laboratory monitoring protocol
        <br/>
        • Obtain baseline measurements before initiating combined therapy
        <br/>
        • Schedule follow-up assessments at appropriate intervals (typically 1-2 weeks initially)
        <br/>
        • Document patient education regarding warning signs and symptoms
        <br/><br/>
        
        <b>Patient Counseling:</b>
        <br/>
        Provide comprehensive education regarding:
        <br/>
        • Nature of the interaction and potential consequences
        <br/>
        • Importance of adherence to prescribed regimen
        <br/>
        • Signs and symptoms requiring immediate medical attention
        <br/>
        • Avoidance of self-medication with OTC drugs or supplements without consultation
        """
        story.append(Paragraph(management_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 5: Evidence Base
        story.append(Paragraph("5. Evidence Base and Limitations", self.styles['SectionHeading']))
        
        story.append(Paragraph("5.1 Methodology", self.styles['SubsectionHeading']))
        methodology_text = """
        This analysis utilizes a dual-AI architecture:
        <br/><br/>
        <b>Classification Model:</b> Fine-tuned BioBERT (Bidirectional Encoder Representations from 
        Transformers for Biomedical Text Mining) trained on the DDI Extraction 2013 Corpus, containing 
        annotated drug-drug interactions from DrugBank and MEDLINE abstracts.
        <br/><br/>
        <b>Generation Model:</b> BioGPT (Generative Pre-trained Transformer for Biomedical Text), 
        pre-trained on 15 million PubMed abstracts, used for evidence-based report synthesis.
        <br/><br/>
        The system performs relation classification to identify interaction type and severity, followed 
        by contextual report generation based on biomedical knowledge encoded in the models.
        """
        story.append(Paragraph(methodology_text, self.styles['CustomBody']))
        
        story.append(Paragraph("5.2 Clinical Validation and Limitations", self.styles['SubsectionHeading']))
        limitations_text = """
        <b>Important Considerations:</b>
        <br/><br/>
        • This is an AI-generated analysis and should be considered as decision support rather than 
        definitive clinical guidance
        <br/><br/>
        • The models are trained on published literature and may not include the most recent evidence 
        or rare drug interactions
        <br/><br/>
        • Individual patient factors (genetic polymorphisms, age, organ function, disease states, 
        concomitant medications) significantly influence interaction risk and severity
        <br/><br/>
        • The absence of a predicted interaction does not guarantee safety, as novel or rare 
        interactions may not be well-documented in the training data
        <br/><br/>
        • Clinical judgment and patient-specific assessment remain paramount in decision-making
        <br/><br/>
        <b>Recommended Additional Resources:</b>
        <br/>
        • Consult primary literature and systematic reviews for detailed evidence
        <br/>
        • Refer to drug prescribing information and FDA labeling
        <br/>
        • Utilize established drug interaction databases (e.g., Lexicomp, Micromedex)
        <br/>
        • Consider consultation with clinical pharmacist or specialist when managing complex cases
        """
        story.append(Paragraph(limitations_text, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Section 6: References and Reporting
        story.append(PageBreak())
        story.append(Paragraph("6. Documentation and Adverse Event Reporting", self.styles['SectionHeading']))
        
        documentation_text = """
        <b>Clinical Documentation:</b>
        <br/>
        Document in the medical record:
        <br/>
        • Recognition of potential drug-drug interaction
        <br/>
        • Risk-benefit assessment for continuing therapy
        <br/>
        • Management plan implemented (dose adjustment, monitoring, alternative therapy)
        <br/>
        • Patient education provided
        <br/>
        • Follow-up plan and monitoring schedule
        <br/><br/>
        
        <b>Adverse Event Reporting:</b>
        <br/>
        If an adverse event occurs that may be related to this drug interaction:
        <br/>
        • Report to FDA MedWatch: www.fda.gov/medwatch or 1-800-FDA-1088
        <br/>
        • Report to respective pharmaceutical manufacturers
        <br/>
        • Document thoroughly in patient chart and institutional adverse event reporting system
        <br/>
        • Consider reporting to relevant pharmacovigilance databases
        <br/><br/>
        
        <b>System Information:</b>
        <br/>
        Report Generated by: BioGPT-DI Clinical Decision Support System
        <br/>
        Version: 1.0
        <br/>
        Models: Fine-tuned BioBERT-v1.1 + BioGPT
        <br/>
        Generated: {date}
        <br/><br/>
        
        <b>Disclaimer:</b>
        <br/>
        This report is intended for use by licensed healthcare professionals as a clinical decision 
        support tool. It does not constitute medical advice and should not replace clinical judgment. 
        The user is responsible for verifying all information and making treatment decisions based on 
        comprehensive patient assessment and current evidence-based guidelines.
        """.format(date=date_str)
        story.append(Paragraph(documentation_text, self.styles['BodyText']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer