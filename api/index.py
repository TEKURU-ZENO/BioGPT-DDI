from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os

app = FastAPI(title="BioGPT-DI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hugging Face configuration
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")  # Add this to Vercel Environment Variables
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

async def query_huggingface(model_id: str, inputs: str):
    """Query Hugging Face Inference API"""
    API_URL = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(API_URL, headers=headers, json={"inputs": inputs})
        return response.json()

@app.get("/")
def read_root():
    return {"message": "BioGPT-DI API is running", "status": "healthy"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/predict", response_model=PredictionResponse)
async def predict_interaction(request: PredictionRequest):
    """
    Predict drug-drug interaction using Hugging Face Inference API
    """
    try:
        drug1 = request.drug1.strip()
        drug2 = request.drug2.strip()
        
        if not drug1 or not drug2:
            raise HTTPException(status_code=400, detail="Both drug names are required")
        
        # Step 1: Predict interaction type with BioBERT
        input_text = f"{drug1} and {drug2} interaction"
        
        # For now, return mock response (you can add HF API call later)
        # prediction_result = await query_huggingface(BIOBERT_MODEL, input_text)
        
        # Mock response for testing
        interaction_type = "EFFECT"
        severity = "Moderate"
        
        # Step 2: Generate reports with BioGPT
        professional_prompt = f"Explain the drug interaction between {drug1} and {drug2} for healthcare professionals. Include mechanism and clinical significance."
        patient_prompt = f"Explain in simple terms what happens when {drug1} and {drug2} are taken together."
        
        # professional_report_result = await query_huggingface(BIOGPT_MODEL, professional_prompt)
        # patient_report_result = await query_huggingface(BIOGPT_MODEL, patient_prompt)
        
        # Mock reports
        professional_report = f"Drug-drug interaction detected between {drug1} and {drug2}. Type: {interaction_type}. The interaction may result from pharmacokinetic alterations affecting drug metabolism or pharmacodynamic synergy/antagonism. Clinical monitoring is recommended, particularly for signs of altered drug efficacy or adverse effects. Dose adjustments may be necessary based on patient response and therapeutic drug monitoring where applicable."
        
        patient_report = f"When {drug1} and {drug2} are taken together, they may interact with each other. This means one drug might change how the other works in your body. Please tell your doctor or pharmacist about all medications you're taking. They can advise you on the safest way to take these medicines together, or suggest alternatives if needed."
        
        return PredictionResponse(
            prediction=interaction_type,
            severity=severity,
            patient_report=patient_report,
            professional_report=professional_report
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

# Vercel serverless handler (optional, FastAPI works without it)
# from mangum import Mangum
# handler = Mangum(app)
