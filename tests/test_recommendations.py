"""Unit tests for recommendation engine service."""

import numpy as np
import pandas as pd
import pytest
from backend.config import (
    PREFERENCE_BEST_BALANCE,
    PREFERENCE_CHEAPEST,
    PREFERENCE_HIGHEST_AVAILABILITY,
    PREFERENCE_NEAREST,
)
from backend.model_service import load_model
from backend.recommendation_service import (
    apply_user_preference,
    assign_availability_status,
    assign_confidence_label,
    calculate_recommendation_scores,
    get_top_recommendations,
)


def test_assign_availability_status():
    """Verify threshold classification."""
    assert assign_availability_status(0.85) == "High"
    assert assign_availability_status(0.60) == "High"
    assert assign_availability_status(0.59) == "Medium"
    assert assign_availability_status(0.25) == "Medium"
    assert assign_availability_status(0.24) == "Low"
    assert assign_availability_status(0.0) == "Low"


def test_assign_confidence_label():
    """Verify confidence heuristic based on historical deviation."""
    assert assign_confidence_label(50, hist_mean=50, hist_std=10, hist_count=100) == "High"
    assert assign_confidence_label(70, hist_mean=50, hist_std=10, hist_count=100) == "Medium"
    assert assign_confidence_label(90, hist_mean=50, hist_std=10, hist_count=100) == "Low"
    assert assign_confidence_label(50, hist_mean=50, hist_std=10, hist_count=5) == "Low"


def test_calculate_recommendation_scores_bounds():
    """Verify predicted spaces never exceed total spaces and scores are bounded [0, 1]."""
    model = load_model()

    sample_df = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-15 10:00:00",
                "parking_id": "P1",
                "parking_name": "Central Mall Parking",
                "parking_type": "Mall",
                "latitude": 12.9719,
                "longitude": 77.5937,
                "total_spaces": 200,
                "occupied_spaces": 100,
                "available_spaces": 100,
                "occupancy_rate": 0.5,
                "distance_km": 0.8,
                "price_per_hour": 40,
                "traffic_level": "medium",
                "weather": "clear",
                "is_weekend": 0,
                "is_peak_hour": 1,
                "event_flag": 0,
                "data_source": "simulated",
            },
            {
                "timestamp": "2026-01-15 10:00:00",
                "parking_id": "P2",
                "parking_name": "City Office Parking",
                "parking_type": "Office",
                "latitude": 12.9750,
                "longitude": 77.5945,
                "total_spaces": 150,
                "occupied_spaces": 120,
                "available_spaces": 30,
                "occupancy_rate": 0.8,
                "distance_km": 1.4,
                "price_per_hour": 30,
                "traffic_level": "medium",
                "weather": "clear",
                "is_weekend": 0,
                "is_peak_hour": 1,
                "event_flag": 0,
                "data_source": "simulated",
            },
        ]
    )

    scored = calculate_recommendation_scores(sample_df, model)

    assert (scored["predicted_available_spaces"] >= 0).all()
    assert (scored["predicted_available_spaces"] <= scored["total_spaces"]).all()
    assert (scored["availability_score"] >= 0.0).all() and (scored["availability_score"] <= 1.0).all()
    assert (scored["recommendation_score"] >= 0.0).all() and (scored["recommendation_score"] <= 1.0).all()


def test_preference_sorting():
    """Verify preference sorting behavior."""
    scored_dummy = pd.DataFrame(
        {
            "parking_name": ["Lot A", "Lot B", "Lot C"],
            "parking_type": ["Mall", "Street", "Transit"],
            "recommendation_score": [0.70, 0.90, 0.60],
            "availability_score": [0.80, 0.40, 0.95],
            "distance_km": [2.0, 0.5, 1.2],
            "price_per_hour": [50, 20, 10],
            "availability_status": ["High", "Medium", "High"],
        }
    )

    # Best balance
    bb = apply_user_preference(scored_dummy, PREFERENCE_BEST_BALANCE)
    assert bb.iloc[0]["parking_name"] == "Lot B"

    # Highest availability
    ha = apply_user_preference(scored_dummy, PREFERENCE_HIGHEST_AVAILABILITY)
    assert ha.iloc[0]["parking_name"] == "Lot C"

    # Nearest
    nr = apply_user_preference(scored_dummy, PREFERENCE_NEAREST)
    assert nr.iloc[0]["parking_name"] == "Lot B"

    # Cheapest
    ch = apply_user_preference(scored_dummy, PREFERENCE_CHEAPEST)
    assert ch.iloc[0]["parking_name"] == "Lot C"


def test_get_top_recommendations_limit():
    """Verify top 3 recommendation limit and rank assignment."""
    dummy_df = pd.DataFrame(
        {
            "parking_name": [f"Lot {i}" for i in range(5)],
            "parking_type": ["Mall", "Street", "Transit", "Office", "Campus"],
            "recommendation_score": [0.5, 0.6, 0.7, 0.8, 0.9],
            "availability_score": [0.5, 0.6, 0.7, 0.8, 0.9],
            "distance_km": [1.0, 1.5, 2.0, 2.5, 3.0],
            "price_per_hour": [20, 25, 30, 35, 40],
            "availability_status": ["Medium", "High", "High", "High", "High"],
        }
    )
    top = get_top_recommendations(dummy_df, preference=PREFERENCE_BEST_BALANCE, top_n=3)
    assert len(top) == 3
    assert list(top["rank"]) == [1, 2, 3]
    assert top.iloc[0]["parking_name"] == "Lot 4"
    assert "explanation" in top.columns
