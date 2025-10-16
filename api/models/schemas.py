from pydantic import BaseModel

class DDIRequest(BaseModel):
    drug1: str
    drug2: str

class DDIResponse(BaseModel):
    prediction: str
    severity: str
    professional_report: str
    patient_report: str