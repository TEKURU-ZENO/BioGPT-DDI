from api.ml import ddi_predictor, report_generator

def create_ddi_reports(drug1: str, drug2: str) -> dict:
    """Orchestrates the DDI prediction and report generation process."""
    
    interaction_type = ddi_predictor.predict_interaction(drug1, drug2)

    # Mock Severity Assessment based on the predicted interaction type
    severity_map = {
        "MECHANISM": "Major",
        "EFFECT": "Moderate",
        "ADVICE": "Moderate",
        "INT": "Minor"
    }
    severity = severity_map.get(interaction_type, "Unknown")

    # Generate Professional Report
    professional_prompt = f"Generate a professional clinical summary for a pharmacist about a '{interaction_type}' interaction between {drug1} and {drug2}, detailing the potential mechanism and clinical effects."
    professional_report = report_generator.generate_report(professional_prompt)

    # Generate Patient-Friendly Report
    patient_prompt = f"Generate a simple, easy-to-understand summary for a patient about a '{interaction_type}' drug interaction between {drug1} and {drug2}. Explain what to watch for and advise them to talk to their doctor."
    patient_report = report_generator.generate_report(patient_prompt)

    return {
        "prediction": interaction_type,
        "severity": severity,
        "professional_report": professional_report,
        "patient_report": patient_report
    }