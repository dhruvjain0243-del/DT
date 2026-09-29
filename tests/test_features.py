"""Unit tests for feature engineering service."""

import pandas as pd
import pytest
from backend.config import MODEL_FEATURES, TARGET_COLUMN
from backend.feature_service import (
    create_prediction_target,
    create_time_features,
    get_model_features,
)


def test_create_time_features():
    """Verify time features extraction from timestamp."""
    df = pd.DataFrame({"timestamp": ["2026-01-01 08:30:00", "2026-01-03 14:00:00"]})
    df_feat = create_time_features(df)

    assert "hour" in df_feat.columns
    assert "minute" in df_feat.columns
    assert "day_of_week" in df_feat.columns
    assert "is_weekend" in df_feat.columns

    assert df_feat.loc[0, "hour"] == 8
    assert df_feat.loc[0, "minute"] == 30
    assert df_feat.loc[0, "is_weekend"] == 0  # Jan 1 2026 was Thursday

    assert df_feat.loc[1, "hour"] == 14
    assert df_feat.loc[1, "minute"] == 0
    assert df_feat.loc[1, "is_weekend"] == 1  # Jan 3 2026 was Saturday


def test_create_prediction_target():
    """Verify target_available_30min is 1-step lead of available_spaces per location."""
    df = pd.DataFrame(
        {
            "parking_id": ["P1", "P1", "P1", "P2", "P2"],
            "timestamp": [
                "2026-01-01 08:00:00",
                "2026-01-01 08:30:00",
                "2026-01-01 09:00:00",
                "2026-01-01 08:00:00",
                "2026-01-01 08:30:00",
            ],
            "available_spaces": [100, 90, 80, 50, 45],
        }
    )
    df_target = create_prediction_target(df)

    assert TARGET_COLUMN in df_target.columns
    # Last row of each group dropped because future target is NaN
    assert len(df_target) == 3

    # For P1 at 08:00, target is 90
    p1_0800 = df_target[(df_target["parking_id"] == "P1") & (df_target["timestamp"] == "2026-01-01 08:00:00")]
    assert p1_0800[TARGET_COLUMN].values[0] == 90

    # For P1 at 08:30, target is 80
    p1_0830 = df_target[(df_target["parking_id"] == "P1") & (df_target["timestamp"] == "2026-01-01 08:30:00")]
    assert p1_0830[TARGET_COLUMN].values[0] == 80

    # For P2 at 08:00, target is 45
    p2_0800 = df_target[(df_target["parking_id"] == "P2") & (df_target["timestamp"] == "2026-01-01 08:00:00")]
    assert p2_0800[TARGET_COLUMN].values[0] == 45


def test_get_model_features_excludes_leakage():
    """Verify model features contain only allowed predictors."""
    df = pd.DataFrame(
        {
            "timestamp": ["2026-01-01 08:00:00"],
            "parking_id": ["P1"],
            "total_spaces": [100],
            "occupied_spaces": [30],
            "available_spaces": [70],
            "occupancy_rate": [0.3],
            "distance_km": [1.2],
            "price_per_hour": [30],
            "event_flag": [0],
            "target_available_30min": [65],
        }
    )
    X = get_model_features(df)
    assert list(X.columns) == MODEL_FEATURES
    assert "available_spaces" not in X.columns
    assert "occupancy_rate" not in X.columns
    assert "target_available_30min" not in X.columns
    assert "timestamp" not in X.columns
