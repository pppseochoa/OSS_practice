import os
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from ml.models import load_model, UntrainedSalaryModel

app = FastAPI(title="KBO Salary Prediction API", version="0.1.0")
origins = [value.strip() for value in os.environ.get("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["POST"], allow_headers=["*"])

class PredictionRequest(BaseModel):
    player_type: Literal["batter", "pitcher"]
    stats: dict[str, float] = Field(min_length=1)

@app.get("/health")
def health():
    model = load_model()
    return {"status": "ok", "model_status": model.status if isinstance(model, UntrainedSalaryModel) else model["status"]}

@app.post("/api/v1/predict")
def predict(request: PredictionRequest):
    if any(value < 0 for value in request.stats.values()): raise HTTPException(422, "성적은 음수일 수 없습니다.")
    model = load_model()
    if isinstance(model, UntrainedSalaryModel): salary, status = model.predict(request.player_type, request.stats), model.status
    else:
        row = [request.stats.get(name, 0) for name in model["features"]]
        salary, status = int(max(1, model["pipeline"].predict([row])[0])), model["status"]
    return {"suggested_salary_krw": salary, "model_status": status, "currency": "KRW"}
