import joblib
from ml.models import MODEL_PATH, UntrainedSalaryModel

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(UntrainedSalaryModel(), MODEL_PATH)
print(f"Prepared untrained model: {MODEL_PATH}")
