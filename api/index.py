from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import os
from api.utils.pdf_generator import DDIReportGenerator

app = FastAPI(title="BioGPT-DI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PDF generator
pdf_generator = DDIReportGenerator()

# Hugging Face configuration
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
BIOBERT_MODEL = "tekuru/biogpt-ddi-focal"
BIOGPT_MODEL = "microsoft/biogpt"

class PredictionRequest(BaseModel):
    drug1: str
    drug2: str

class PredictionResponse(BaseModel):
    prediction: str
    severity: str
    patient_report: str
    professional_report: str

class PDFRequest(BaseModel):
    drug1: str
    drug2: str
    report_type: str  # "patient" or "professional"
    prediction_data: dict

async def query_huggingface(model_id: str, inputs: str):
    """Query Hugging Face Inference API"""
    API_URL = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(API_URL, headers=headers, json={"inputs": inputs})
        return response.json()

async def generate_detailed_report(drug1: str, drug2: str, report_type: str, interaction_type: str) -> str:
    """Generate detailed reports using BioGPT"""
    
    if report_type == "patient":
        prompt = f"""Explain in simple, patient-friendly language what happens when {drug1} and {drug2} are taken together.
        
The interaction is classified as: {interaction_type}

Include:
1. What this interaction means in everyday terms
2. How these drugs might affect each other in the body
3. What symptoms or changes to watch for
4. Why this interaction happens
5. What patients should discuss with their healthcare provider

Use simple language without medical jargon. Be thorough but easy to understand."""
        
    else:  # professional
        prompt = f"""Provide a detailed clinical analysis of the drug-drug interaction between {drug1} and {drug2}.

The interaction is classified as: {interaction_type}

Include:
1. Detailed pharmacokinetic and pharmacodynamic mechanisms
2. Clinical significance and potential outcomes
3. Specific monitoring parameters and frequency
4. Evidence-based management strategies
5. Risk stratification and dose adjustment recommendations
6. Alternative therapy considerations

Provide a comprehensive clinical perspective suitable for healthcare professionals."""
    
    try:
        # Query BioGPT for detailed generation
        result = await query_huggingface(BIOGPT_MODEL, prompt)
        
        # Extract generated text
        if isinstance(result, list) and len(result) > 0:
            return result[0].get('generated_text', prompt)
        elif isinstance(result, dict):
            return result.get('generated_text', prompt)
        else:
            return prompt  # Fallback to prompt if generation fails
            
    except Exception as e:
        print(f"Error generating detailed report: {str(e)}")
        return prompt  # Fallback

@app.get("/")
def read_root():
    return {"message": "BioGPT-DI API is running", "status": "healthy"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/predict", response_model=PredictionResponse)
async def predict_interaction(request: PredictionRequest):
    """
    Predict drug-drug interaction
    """
    try:
        drug1 = request.drug1.strip()
        drug2 = request.drug2.strip()
        
        if not drug1 or not drug2:
            raise HTTPException(status_code=400, detail="Both drug names are required")
        
        # Step 1: Predict interaction type with BioBERT
        input_text = f"{drug1} and {drug2} interaction"
        
        # Mock classification for now (replace with actual HF API call)
        interaction_type = "EFFECT"
        severity = "Moderate"
        
        # Step 2: Generate detailed reports
        professional_report = await generate_detailed_report(
            drug1, drug2, "professional", interaction_type
        )
        
        patient_report = await generate_detailed_report(
            drug1, drug2, "patient", interaction_type
        )
        
        return PredictionResponse(
            prediction=interaction_type,
            severity=severity,
            patient_report=patient_report,
            professional_report=professional_report
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/api/generate-pdf")
async def generate_pdf_report(request: PDFRequest):
    """
    Generate detailed PDF report based on user type (patient or professional)
    """
    try:
        drug1 = request.drug1.strip()
        drug2 = request.drug2.strip()
        report_type = request.report_type.lower()
        prediction_data = request.prediction_data
        
        if report_type not in ["patient", "professional"]:
            raise HTTPException(
                status_code=400, 
                detail="report_type must be 'patient' or 'professional'"
            )
        
        # Generate PDF based on report type
        if report_type == "patient":
            pdf_buffer = pdf_generator.generate_patient_report(
                drug1, drug2, prediction_data
            )
            filename = f"DDI_Report_Patient_{drug1}_{drug2}.pdf"
        else:
            pdf_buffer = pdf_generator.generate_professional_report(
                drug1, drug2, prediction_data
            )
            filename = f"DDI_Report_Professional_{drug1}_{drug2}.pdf"
        
        # Return PDF as streaming response
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
