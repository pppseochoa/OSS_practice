"""Fail fast if model/dependencies cannot load or either player type fails."""
from importlib.metadata import version
from api.main import PredictionRequest, predict
from ml.models import load_model


def main():
    # Import the real future training stack as well as the baseline dependencies.
    import numpy
    import pandas
    import scipy
    import sklearn
    from ml.train import FEATURES

    model = load_model()
    if model is None or len(FEATURES) != 12:
        raise RuntimeError("Invalid model or training feature schema")
    for kind, stats in (
        ("batter", {"games": 120, "plate_appearances": 450, "batting_average": .285, "home_runs": 15, "rbi": 70, "stolen_bases": 10}),
        ("pitcher", {"games_pitched": 25, "innings_pitched": 150, "wins": 10, "saves": 0, "era": 3.5, "strikeouts": 120}),
    ):
        response = predict(PredictionRequest(player_type=kind, stats=stats))
        salary = response["suggested_salary_krw"]
        if type(salary) is not int or salary <= 0:
            raise RuntimeError(f"Invalid {kind} prediction: {salary}")
        print(f"Model load/prediction OK: {kind}={salary} KRW; {response['model_status']}")
    for name in ("Django", "fastapi", "scikit-learn", "numpy", "scipy", "pandas", "joblib"):
        print(f"{name}=={version(name)}")


if __name__ == "__main__":
    main()
