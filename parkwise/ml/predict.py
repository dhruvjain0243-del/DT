from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one trusted local PARKWISE model inference")
    parser.add_argument("--model", type=Path, default=Path("ml/artifacts/parking_model.pkl"))
    parser.add_argument("--features", type=Path, default=Path("ml/artifacts/feature_columns.json"))
    parser.add_argument("--input-json", required=True, help="JSON object containing model feature values")
    args = parser.parse_args()
    columns = json.loads(args.features.read_text(encoding="utf-8"))
    values = json.loads(args.input_json)
    missing = [column for column in columns if column not in values]
    if missing:
        raise SystemExit(f"Missing features: {', '.join(missing)}")
    model = joblib.load(args.model)
    prediction = float(model.predict(pd.DataFrame([values], columns=columns))[0])
    print(json.dumps({"predicted_available_spaces": max(0, round(prediction))}))


if __name__ == "__main__":
    main()
