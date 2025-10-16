from fastapi import APIRouter, HTTPException
from api.models.schemas import DDIRequest, DDIResponse
from api.services import prediction_service

router = APIRouter()

@router.post("/predict", response_model=DDIResponse)
async def predict_interaction_endpoint(request: DDIRequest):
    if not request.drug1 or not request.drug2:
        raise HTTPException(status_code=400, detail="Both drug names must be provided.")
    try:
        reports = prediction_service.create_ddi_reports(request.drug1, request.drug2)
        return reports
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))