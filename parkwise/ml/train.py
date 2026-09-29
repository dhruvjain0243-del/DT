from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


FEATURES = [
    "hour",
    "minute",
    "day_of_week",
    "is_weekend",
    "is_peak_hour",
    "total_spaces",
    "occupied_spaces",
    "distance_km",
    "price_per_hour",
    "event_flag",
]


def prepare(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    frame = frame.sort_values(["parking_id", "timestamp"])
    frame["hour"] = frame["timestamp"].dt.hour
    frame["minute"] = frame["timestamp"].dt.minute
    frame["day_of_week"] = frame["timestamp"].dt.dayofweek
    frame["target_available_30min"] = frame.groupby("parking_id")["available_spaces"].shift(-1)
    return frame.dropna(subset=["target_available_30min"])


def train(dataset: Path, output_dir: Path) -> dict[str, float | int | str]:
    frame = prepare(pd.read_csv(dataset))
    split = int(len(frame) * 0.8)
    train_frame, test_frame = frame.iloc[:split], frame.iloc[split:]
    model = RandomForestRegressor(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
    model.fit(train_frame[FEATURES], train_frame["target_available_30min"])
    predicted = model.predict(test_frame[FEATURES])
    baseline_map = train_frame.groupby("parking_id")["available_spaces"].mean()
    baseline = test_frame["parking_id"].map(baseline_map).fillna(train_frame["available_spaces"].mean())
    metrics = {
        "baseline_mae": round(float(mean_absolute_error(test_frame["target_available_30min"], baseline)), 4),
        "model_mae": round(float(mean_absolute_error(test_frame["target_available_30min"], predicted)), 4),
        "model_rmse": round(float(mean_squared_error(test_frame["target_available_30min"], predicted) ** 0.5), 4),
        "model_r2": round(float(r2_score(test_frame["target_available_30min"], predicted)), 4),
        "train_rows": len(train_frame),
        "test_rows": len(test_frame),
        "dataset_type": "simulated",
        "prediction_horizon_minutes": 30,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_dir / "parking_model.pkl")
    (output_dir / "feature_columns.json").write_text(json.dumps(FEATURES, indent=2), encoding="utf-8")
    (output_dir.parent / "model_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the PARKWISE 30-minute model")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("ml/artifacts"))
    args = parser.parse_args()
    print(json.dumps(train(args.data, args.output), indent=2))


if __name__ == "__main__":
    main()
