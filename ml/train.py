"""실제 CSV 학습: python -m ml.train data/salaries.csv"""
import sys
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from ml.models import MODEL_PATH

FEATURES = ["games", "plate_appearances", "batting_average", "home_runs", "rbi", "stolen_bases", "games_pitched", "innings_pitched", "wins", "saves", "era", "strikeouts"]
if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("Usage: python -m ml.train data/salaries.csv")
    df = pd.read_csv(sys.argv[1]); missing = set(FEATURES + ["next_salary_krw"]) - set(df.columns)
    if missing: raise SystemExit(f"CSV required columns missing: {sorted(missing)}")
    pipeline = Pipeline([("fill", SimpleImputer(strategy="median")), ("regressor", RandomForestRegressor(n_estimators=300, random_state=42))])
    pipeline.fit(df[FEATURES], df["next_salary_krw"])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"status": "trained", "features": FEATURES, "pipeline": pipeline}, MODEL_PATH)
