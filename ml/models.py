from pathlib import Path
import joblib

MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "salary_model.joblib"

class UntrainedSalaryModel:
    """학습 데이터 준비 전 개발·연동 검증용 모델이며 실제 계약 판단용이 아닙니다."""
    status = "untrained_baseline"
    def predict(self, player_type: str, stats: dict) -> int:
        volume = sum(max(0, float(value)) for value in stats.values())
        return int((30_000_000 if player_type == "batter" else 35_000_000) + min(volume, 1_000) * 10_000)

def load_model():
    if not MODEL_PATH.exists(): raise FileNotFoundError("모델 아티팩트가 없습니다. python -m ml.prepare_model 을 실행하세요.")
    return joblib.load(MODEL_PATH)
