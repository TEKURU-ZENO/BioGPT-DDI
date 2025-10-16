from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import predict

app = FastAPI(
    title="BioGPT-DI API",
    description="API for Drug-Drug Interaction Prediction and Report Generation.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to the BioGPT-DI API"}