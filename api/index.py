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

async def query_huggingface(model_id: str, inputs: dict, use_token: bool = True):
    """Query Hugging Face Inference API"""
    API_URL = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {}
    
    if use_token and HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(API_URL, headers=headers, json=inputs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"HF API Error for {model_id}: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return None

async def classify_interaction(drug1: str, drug2: str):
    """Use BioBERT to classify the drug interaction"""
    
    text_input = f"{drug1} and {drug2}"
    
    result = await query_huggingface(
        BIOBERT_MODEL,
        {"inputs": text_input}
    )
    
    if result and isinstance(result, list) and len(result) > 0:
        prediction = result[0]
        if isinstance(prediction, list):
            prediction = prediction[0]
        
        interaction_type = prediction.get('label', 'EFFECT')
        confidence = prediction.get('score', 0.5)
        
        # Map confidence to severity
        if interaction_type in ['MECHANISM', 'EFFECT'] and confidence > 0.8:
            severity = "Major"
        elif confidence > 0.6:
            severity = "Moderate"
        else:
            severity = "Minor"
            
        print(f"[Classification] Type: {interaction_type}, Confidence: {confidence:.2f}, Severity: {severity}")
        return interaction_type, severity
    
    print("[Classification] Using fallback values")
    return "EFFECT", "Moderate"

async def generate_patient_explanation(drug1: str, drug2: str, interaction_type: str, severity: str):
    """Generate unique patient-friendly explanation using BioGPT"""
    
    prompt = f"""Question: What happens when a patient takes {drug1} and {drug2} together?

Answer: When taking {drug1} with {drug2},"""
    
    result = await query_huggingface(
        BIOGPT_MODEL,
        {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 150,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True,
                "return_full_text": False
            }
        }
    )
    
    if result and isinstance(result, list) and len(result) > 0:
        generated_text = result[0].get('generated_text', '')
        
        if generated_text:
            generated_text = generated_text.replace(prompt, '').strip()
            
            if not generated_text.startswith("When taking"):
                generated_text = f"When taking {drug1} with {drug2}, {generated_text}"
            
            print(f"[Patient Report] Generated {len(generated_text)} characters")
            return generated_text
    
    print("[Patient Report] Using fallback")
    return f"Taking {drug1} with {drug2} may cause a {severity.lower()}-severity interaction. This means the drugs may affect how each other works in your body. The interaction is classified as {interaction_type} type, which may involve changes in drug absorption, metabolism, or effects. Please consult your healthcare provider for personalized guidance on taking these medications together safely."

async def generate_professional_explanation(drug1: str, drug2: str, interaction_type: str, severity: str):
    """Generate unique professional explanation using BioGPT"""
    
    prompt = f"""Clinical drug interaction assessment for {drug1} and {drug2}:

Mechanism: The interaction"""
    
    result = await query_huggingface(
        BIOGPT_MODEL,
        {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 200,
                "temperature": 0.6,
                "top_p": 0.85,
                "do_sample": True,
                "return_full_text": False
            }
        }
    )
    
    if result and isinstance(result, list) and len(result) > 0:
        generated_text = result[0].get('generated_text', '')
        
        if generated_text:
            generated_text = generated_text.replace(prompt, '').strip()
            
            if not generated_text.startswith("The"):
                generated_text = f"The interaction {generated_text}"
            
            clinical_summary = f"The concurrent use of {drug1} and {drug2} presents a {severity.lower()}-severity drug-drug interaction classified as {interaction_type}. {generated_text}"
            
            print(f"[Professional Report] Generated {len(clinical_summary)} characters")
            return clinical_summary
    
    print("[Professional Report] Using fallback")
    return f"The concurrent use of {drug1} and {drug2} presents a {severity.lower()}-severity interaction classified as {interaction_type}. This interaction may involve pharmacokinetic alterations (affecting absorption, distribution, metabolism, or excretion) or pharmacodynamic effects (affecting drug receptor interactions or physiological responses). Clinical monitoring, potential dose adjustment, and assessment of therapeutic alternatives are recommended. Implement enhanced monitoring protocols and document risk-benefit assessment in patient record."

@app.get("/")
def read_root():
    return {
        "message": "BioGPT-DI API is running",
        "status": "healthy",
        "version": "1.0.0"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "hf_token_configured": bool(HF_API_TOKEN),
        "models": {
            "classification": BIOBERT_MODEL,
            "generation": BIOGPT_MODEL
        }
    }

@app.post("/api/predict", response_model=PredictionResponse)
async def predict_interaction(request: PredictionRequest):
    """
    Predict drug-drug interaction with AI-generated unique explanations
    """
    try:
        drug1 = request.drug1.strip().title()
        drug2 = request.drug2.strip().title()
        
        if not drug1 or not drug2:
            raise HTTPException(status_code=400, detail="Both drug names are required")
        
        print(f"\n{'='*60}")
        print(f"[ANALYSIS START] {drug1} + {drug2}")
        print(f"{'='*60}")
        
        # Step 1: Classify interaction
        print("[Step 1/3] Classifying interaction with BioBERT...")
        interaction_type, severity = await classify_interaction(drug1, drug2)
        
        # Step 2: Generate patient explanation
        print("[Step 2/3] Generating patient explanation with BioGPT...")
        patient_report = await generate_patient_explanation(
            drug1, drug2, interaction_type, severity
        )
        
        # Step 3: Generate professional explanation
        print("[Step 3/3] Generating professional explanation with BioGPT...")
        professional_report = await generate_professional_explanation(
            drug1, drug2, interaction_type, severity
        )
        
        print(f"[ANALYSIS COMPLETE] Type: {interaction_type}, Severity: {severity}")
        print(f"{'='*60}\n")
        
        return PredictionResponse(
            prediction=interaction_type,
            severity=severity,
            patient_report=patient_report,
            professional_report=professional_report
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. The AI models may be loading (cold start - typically takes 30-60 seconds on first request). Please try again in a moment."
        )

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
        
        print(f"[PDF Generation] Type: {report_type}, Drugs: {drug1} + {drug2}")
        
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
        
        print(f"[PDF Generated] {filename}")
        
        # Return PDF as streaming response
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        print(f"[PDF Error] {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(e)}"
        )
