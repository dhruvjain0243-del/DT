"""
Machine learning model service for PARKWISE.
Handles model training (Random Forest + historical baseline),
metric evaluation, artifact persistence, and prediction inference.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.config import (
    FEATURE_COLUMNS_PATH,
    METRICS_PATH,
    MODEL_FEATURES,
    MODEL_PATH,
    PREDICTION_HORIZON_MINUTES,
    TARGET_COLUMN,
)
from backend.data_service import prepare_dataset
from backend.feature_service import (
    create_prediction_target,
    get_model_features,
    save_feature_columns,
)


def train_model(
    df: Optional[pd.DataFrame] = None,
    split_ratio: float = 0.8,
) -> Tuple[RandomForestRegressor, Dict[str, Any]]:
    """
    Train a Random Forest Regressor and a Historical Average baseline.
    Uses chronological split (first 80% train, final 20% test).
    Saves model, feature list, and performance metrics.
    """
    if df is None:
        df = prepare_dataset()

    # Create 30-min target and remove NaN
    df_target = create_prediction_target(df)

    # Sort strictly by timestamp for chronological split
    df_target = df_target.sort_values(by=["timestamp", "parking_id"]).reset_index(drop=True)

    # Split chronologically based on unique timestamps
    unique_timestamps = np.sort(df_target["timestamp"].unique())
    split_idx = int(len(unique_timestamps) * split_ratio)
    split_timestamp = unique_timestamps[split_idx]

    train_mask = df_target["timestamp"] < split_timestamp
    test_mask = df_target["timestamp"] >= split_timestamp

    train_df = df_target[train_mask].copy()
    test_df = df_target[test_mask].copy()

    # 1. Historical-average baseline (per parking_id on training set only)
    baseline_lookup = train_df.groupby("parking_id")["available_spaces"].mean().to_dict()
    test_baseline_preds = test_df["parking_id"].map(baseline_lookup)
    baseline_mae = float(mean_absolute_error(test_df[TARGET_COLUMN], test_baseline_preds))

    # 2. Extract features and target
    X_train = get_model_features(train_df)
    y_train = train_df[TARGET_COLUMN]

    X_test = get_model_features(test_df)
    y_test = test_df[TARGET_COLUMN]

    # 3. Train Random Forest model
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # 4. Evaluate on test set
    y_pred = model.predict(X_test)
    model_mae = float(mean_absolute_error(y_test, y_pred))
    model_mse = mean_squared_error(y_test, y_pred)
    model_rmse = float(np.sqrt(model_mse))
    model_r2 = float(r2_score(y_test, y_pred))

    metrics: Dict[str, Any] = {
        "baseline_mae": round(baseline_mae, 4),
        "model_mae": round(model_mae, 4),
        "model_rmse": round(model_rmse, 4),
        "model_r2": round(model_r2, 4),
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "dataset_type": "simulated",
        "prediction_horizon_minutes": PREDICTION_HORIZON_MINUTES,
    }

    # 5. Persist artifacts
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    save_feature_columns(MODEL_FEATURES, FEATURE_COLUMNS_PATH)

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)

    return model, metrics


def load_model(filepath: Optional[Path] = None) -> RandomForestRegressor:
    """Load the trained Random Forest model from disk."""
    target_path = Path(filepath) if filepath else MODEL_PATH
    if not target_path.exists():
        raise FileNotFoundError(
            f"Trained model not found at '{target_path}'. "
            f"Please run 'python scripts/train_model.py' first."
        )
    try:
        model = joblib.load(target_path)
        return model
    except Exception as e:
        raise RuntimeError(
            f"Error loading model from '{target_path}': {str(e)}. "
            f"Please retrain with 'python scripts/train_model.py'."
        )


def load_metrics(filepath: Optional[Path] = None) -> Dict[str, Any]:
    """Load model metrics from JSON file."""
    target_path = Path(filepath) if filepath else METRICS_PATH
    if not target_path.exists():
        raise FileNotFoundError(
            f"Model metrics file not found at '{target_path}'. "
            f"Please run 'python scripts/train_model.py' to generate metrics."
        )
    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_model_ready() -> Tuple[bool, str]:
    """Check if all required model artifacts exist and are readable."""
    if not MODEL_PATH.exists():
        return False, f"Model file missing ({MODEL_PATH.name}). Run: python scripts/train_model.py"
    if not FEATURE_COLUMNS_PATH.exists():
        return False, f"Feature columns file missing ({FEATURE_COLUMNS_PATH.name}). Run: python scripts/train_model.py"
    if not METRICS_PATH.exists():
        return False, f"Model metrics file missing ({METRICS_PATH.name}). Run: python scripts/train_model.py"
    return True, "Model and artifacts ready."


def make_predictions(
    model: RandomForestRegressor,
    input_df: pd.DataFrame,
) -> np.ndarray:
    """Generate raw model predictions using the strict feature order."""
    X = get_model_features(input_df)
    preds = model.predict(X)
    return preds
