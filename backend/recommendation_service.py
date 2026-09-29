"""
Recommendation engine service for PARKWISE.
Calculates availability scores, distance and price metrics,
composite recommendation scores, confidence heuristics,
and applies user preference sorting to deliver top recommendations.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.config import (
    AVAILABILITY_WEIGHT,
    DISTANCE_WEIGHT,
    HIGH_AVAILABILITY_THRESHOLD,
    MEDIUM_AVAILABILITY_THRESHOLD,
    PREFERENCE_BEST_BALANCE,
    PREFERENCE_CHEAPEST,
    PREFERENCE_HIGHEST_AVAILABILITY,
    PREFERENCE_NEAREST,
    PRICE_WEIGHT,
)
from backend.model_service import make_predictions


def assign_availability_status(availability_score: float) -> str:
    """
    Categorize availability based on defined thresholds:
    - High: >= 0.60
    - Medium: >= 0.25 and < 0.60
    - Low: < 0.25
    """
    if availability_score >= HIGH_AVAILABILITY_THRESHOLD:
        return "High"
    elif availability_score >= MEDIUM_AVAILABILITY_THRESHOLD:
        return "Medium"
    else:
        return "Low"


def assign_confidence_label(
    predicted_spaces: float,
    hist_mean: float,
    hist_std: float,
    hist_count: int = 100,
) -> str:
    """
    Heuristic confidence label indicating whether prediction falls within
    typical historical distribution for this location.
    Note: Not a statistically calibrated probability.
    - High: sufficient historical records and prediction within 1.5 standard deviations.
    - Medium: within 2.5 standard deviations.
    - Low: high variation or extreme prediction.
    """
    if hist_count < 10:
        return "Low"

    std = max(hist_std, 1.0)
    deviation = abs(predicted_spaces - hist_mean) / std

    if deviation <= 1.5:
        return "High"
    elif deviation <= 2.5:
        return "Medium"
    else:
        return "Low"


def generate_explanation(
    parking_name: str,
    status: str,
    distance_km: float,
    price_per_hour: float,
    pref: str,
) -> str:
    """Generate a clean, user-friendly natural language explanation for why this parking is recommended."""
    price_desc = "budget-friendly rates" if price_per_hour <= 20 else "standard pricing"
    dist_desc = "close proximity" if distance_km <= 1.0 else "moderate walking distance"

    if pref == PREFERENCE_HIGHEST_AVAILABILITY:
        return f"{parking_name} offers {status.lower()} predicted capacity ({dist_desc})."
    elif pref == PREFERENCE_NEAREST:
        return f"{parking_name} is situated at {distance_km} km with {status.lower()} available spaces."
    elif pref == PREFERENCE_CHEAPEST:
        return f"{parking_name} has the lowest rate of ₹{price_per_hour}/hr with {status.lower()} availability."
    else:
        return f"{parking_name} is recommended because it combines {status.lower()} availability with {dist_desc} and {price_desc}."


def calculate_recommendation_scores(
    records_df: pd.DataFrame,
    model: Any,
    historical_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Score parking locations based on model predictions, normalized distance, and price.
    Calculates:
    - predicted_available_spaces (clipped to [0, total_spaces])
    - availability_score
    - distance_score
    - price_score
    - recommendation_score
    - availability_status
    - confidence
    """
    df = records_df.copy()

    # Model inference
    raw_preds = make_predictions(model, df)
    # Clip predictions between 0 and total_spaces
    clipped_preds = np.clip(raw_preds, 0, df["total_spaces"].values)
    df["predicted_available_spaces"] = np.round(clipped_preds).astype(int)

    # Calculate availability score
    df["availability_score"] = (
        df["predicted_available_spaces"] / df["total_spaces"]
    ).clip(lower=0.0, upper=1.0)

    # Normalize distance score: 1 - distance_km / max(distance_km)
    max_dist = df["distance_km"].max()
    if max_dist > 0:
        df["distance_score"] = 1.0 - (df["distance_km"] / max_dist)
    else:
        df["distance_score"] = 1.0
    df["distance_score"] = df["distance_score"].clip(lower=0.0, upper=1.0)

    # Normalize price score: 1 - price_per_hour / max(price_per_hour)
    max_price = df["price_per_hour"].max()
    if max_price > 0:
        df["price_score"] = 1.0 - (df["price_per_hour"] / max_price)
    else:
        df["price_score"] = 1.0
    df["price_score"] = df["price_score"].clip(lower=0.0, upper=1.0)

    # Composite recommendation score
    df["recommendation_score"] = (
        AVAILABILITY_WEIGHT * df["availability_score"]
        + DISTANCE_WEIGHT * df["distance_score"]
        + PRICE_WEIGHT * df["price_score"]
    ).round(4)

    # Availability percentage for UI display
    df["availability_pct"] = (df["availability_score"] * 100).round(1)

    # Assign availability status (High, Medium, Low)
    df["availability_status"] = df["availability_score"].apply(assign_availability_status)

    # Calculate confidence labels
    if historical_df is not None and not historical_df.empty:
        stats = (
            historical_df.groupby("parking_id")["available_spaces"]
            .agg(["mean", "std", "count"])
            .to_dict(orient="index")
        )
    else:
        stats = {}

    confidence_list = []
    for _, row in df.iterrows():
        p_id = row["parking_id"]
        p_stat = stats.get(p_id, {"mean": row["available_spaces"], "std": 10.0, "count": 100})
        conf = assign_confidence_label(
            row["predicted_available_spaces"],
            p_stat.get("mean", 50.0),
            p_stat.get("std", 10.0),
            int(p_stat.get("count", 100)),
        )
        confidence_list.append(conf)

    df["confidence"] = confidence_list

    return df


def apply_user_preference(
    scored_df: pd.DataFrame,
    preference: str = PREFERENCE_BEST_BALANCE,
) -> pd.DataFrame:
    """
    Sort scored DataFrame based on selected user preference:
    1. Best balance: Sort by recommendation_score descending
    2. Highest availability: Sort by availability_score descending
    3. Nearest: Sort by distance_km ascending
    4. Cheapest: Sort by price_per_hour ascending
    """
    df = scored_df.copy()

    if preference == PREFERENCE_HIGHEST_AVAILABILITY:
        df = df.sort_values(by=["availability_score", "recommendation_score"], ascending=[False, False])
    elif preference == PREFERENCE_NEAREST:
        df = df.sort_values(by=["distance_km", "recommendation_score"], ascending=[True, False])
    elif preference == PREFERENCE_CHEAPEST:
        df = df.sort_values(by=["price_per_hour", "recommendation_score"], ascending=[True, False])
    else:  # Best balance (default)
        df = df.sort_values(by=["recommendation_score", "availability_score"], ascending=[False, False])

    return df.reset_index(drop=True)


def get_top_recommendations(
    scored_df: pd.DataFrame,
    preference: str = PREFERENCE_BEST_BALANCE,
    top_n: int = 3,
    parking_type_filter: Optional[str] = None,
) -> pd.DataFrame:
    """
    Filter by optional parking type, apply user preference sorting,
    assign rank, and attach natural language explanation.
    """
    df = scored_df.copy()

    if parking_type_filter and parking_type_filter != "All":
        df = df[df["parking_type"] == parking_type_filter]

    sorted_df = apply_user_preference(df, preference)
    top_df = sorted_df.head(top_n).copy().reset_index(drop=True)

    # Assign 1-indexed rank
    top_df["rank"] = range(1, len(top_df) + 1)

    # Generate explanations
    explanations = [
        generate_explanation(
            row["parking_name"],
            row["availability_status"],
            row["distance_km"],
            row["price_per_hour"],
            preference,
        )
        for _, row in top_df.iterrows()
    ]
    top_df["explanation"] = explanations

    return top_df
