"""
Feature engineering service for PARKWISE.
Constructs temporal features, generates the 30-minute ahead target,
and prepares the strict feature matrix for training and inference.
"""

import json
from pathlib import Path
from typing import List, Optional
import pandas as pd

from backend.config import (
    FEATURE_COLUMNS_PATH,
    MODEL_FEATURES,
    TARGET_COLUMN,
)


def create_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract temporal features from timestamp:
    - hour
    - minute
    - day_of_week (0=Monday, 6=Sunday)
    - is_weekend (0 or 1)
    - is_peak_hour (preserves existing or computes standard peak windows)
    """
    df_out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_out["timestamp"]):
        df_out["timestamp"] = pd.to_datetime(df_out["timestamp"])

    df_out["hour"] = df_out["timestamp"].dt.hour
    df_out["minute"] = df_out["timestamp"].dt.minute
    df_out["day_of_week"] = df_out["timestamp"].dt.dayofweek

    # Preserve dataset's is_weekend and is_peak_hour if present, otherwise compute
    if "is_weekend" not in df_out.columns:
        df_out["is_weekend"] = (df_out["day_of_week"] >= 5).astype(int)
    else:
        df_out["is_weekend"] = df_out["is_weekend"].astype(int)

    if "is_peak_hour" not in df_out.columns:
        # Default peak hours: 8-10 AM and 5-7 PM on weekdays
        is_weekday = df_out["is_weekend"] == 0
        morning_peak = (df_out["hour"] >= 8) & (df_out["hour"] < 10)
        evening_peak = (df_out["hour"] >= 17) & (df_out["hour"] < 19)
        df_out["is_peak_hour"] = (is_weekday & (morning_peak | evening_peak)).astype(int)
    else:
        df_out["is_peak_hour"] = df_out["is_peak_hour"].astype(int)

    return df_out


def create_prediction_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create the prediction target: target_available_30min.
    Sorts by parking_id and timestamp, shifts available_spaces by -1,
    and drops rows where target is NaN (i.e. the last timestamp of each location).
    """
    df_sorted = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_sorted["timestamp"]):
        df_sorted["timestamp"] = pd.to_datetime(df_sorted["timestamp"])

    df_sorted = df_sorted.sort_values(by=["parking_id", "timestamp"]).reset_index(drop=True)

    df_sorted[TARGET_COLUMN] = df_sorted.groupby("parking_id")["available_spaces"].shift(-1)

    # Remove rows where target is missing
    df_clean = df_sorted.dropna(subset=[TARGET_COLUMN]).copy()
    df_clean[TARGET_COLUMN] = df_clean[TARGET_COLUMN].astype(float)
    return df_clean.reset_index(drop=True)


def get_model_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract exact ordered features for model input.
    Ensures no target leakage columns (available_spaces, occupancy_rate,
    target_available_30min, timestamp) are included.
    """
    df_features = create_time_features(df)
    for col in MODEL_FEATURES:
        if col not in df_features.columns:
            raise KeyError(f"Required feature column '{col}' is missing from DataFrame.")
    return df_features[MODEL_FEATURES].copy()


def save_feature_columns(
    feature_list: Optional[List[str]] = None,
    output_path: Optional[Path] = None,
) -> Path:
    """Save the ordered feature column names to JSON."""
    cols = feature_list if feature_list is not None else MODEL_FEATURES
    out = Path(output_path) if output_path else FEATURE_COLUMNS_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cols, f, indent=4)
    return out


def load_feature_columns(filepath: Optional[Path] = None) -> List[str]:
    """Load ordered feature column names from JSON."""
    src = Path(filepath) if filepath else FEATURE_COLUMNS_PATH
    if not src.exists():
        raise FileNotFoundError(
            f"Feature columns file not found at '{src}'. "
            f"Please run 'python scripts/train_model.py' to generate model artifacts."
        )
    with open(src, "r", encoding="utf-8") as f:
        return json.load(f)
