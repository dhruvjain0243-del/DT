"""
FastAPI application layer for PARKWISE.
Provides RESTful endpoints for health status, parking locations,
performance metrics, availability recommendations, and user feedback submission.
"""

from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import (
    FEEDBACK_STATUS_OPTIONS,
    PREFERENCE_BEST_BALANCE,
    PREFERENCE_OPTIONS,
)
from backend.data_service import get_latest_records, get_records_at_timestamp, prepare_dataset
from backend.feedback_service import load_feedback, save_feedback
from backend.model_service import check_model_ready, load_metrics, load_model
from backend.recommendation_service import (
    calculate_recommendation_scores,
    get_top_recommendations,
)

app = FastAPI(
    title="PARKWISE API",
    description="Smart Parking Availability Prediction and Recommendation REST API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas
class RecommendationRequest(BaseModel):
    arrival_timestamp: Optional[str] = Field(
        default=None,
        description="Target arrival timestamp in YYYY-MM-DD HH:MM:SS format. If omitted, uses latest record.",
        examples=["2026-01-15 18:00:00"],
    )
    preference: str = Field(
        default=PREFERENCE_BEST_BALANCE,
        description="Ranking preference: 'Best balance', 'Highest availability', 'Nearest', or 'Cheapest'",
    )
    parking_type: Optional[str] = Field(
        default="All",
        description="Optional filter by parking type (e.g. 'Mall', 'Office', 'Transit', 'Campus', 'Street', or 'All')",
    )


class RecommendationItem(BaseModel):
    rank: int
    parking_id: str
    parking_name: str
    parking_type: str
    latitude: float
    longitude: float
    predicted_available_spaces: int
    total_spaces: int
    availability_pct: float
    availability_status: str
    confidence: str
    distance_km: float
    price_per_hour: float
    recommendation_score: float
    explanation: str


class RecommendationResponse(BaseModel):
    success: bool
    timestamp_queried: str
    timestamp_resolved: str
    preference_applied: str
    recommendations: List[RecommendationItem]


class FeedbackRequest(BaseModel):
    parking_id: str = Field(..., description="ID of the parking lot (e.g. 'P1')")
    actual_status: str = Field(
        ...,
        description=f"Observed availability status: {FEEDBACK_STATUS_OPTIONS}",
    )
    comment: Optional[str] = Field(default="", description="Optional user comment")


class FeedbackResponse(BaseModel):
    success: bool
    message: str


# Endpoints
@app.get("/health", summary="Health check endpoint")
def health_check() -> Dict[str, Any]:
    model_ok, model_msg = check_model_ready()
    return {
        "status": "healthy" if model_ok else "degraded",
        "service": "PARKWISE API",
        "version": "1.0.0",
        "model_status": model_msg,
    }


@app.get("/locations", summary="List all configured parking locations")
def get_locations() -> Dict[str, Any]:
    try:
        df = prepare_dataset()
        latest = get_latest_records(df)
        cols = [
            "parking_id",
            "parking_name",
            "parking_type",
            "latitude",
            "longitude",
            "total_spaces",
            "price_per_hour",
            "distance_km",
        ]
        unique_locs = latest[cols].drop_duplicates().to_dict(orient="records")
        return {"success": True, "count": len(unique_locs), "locations": unique_locs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics", summary="Get model performance and evaluation metrics")
def get_metrics() -> Dict[str, Any]:
    try:
        metrics = load_metrics()
        return {"success": True, "metrics": metrics}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommendations", response_model=RecommendationResponse, summary="Get top parking recommendations")
def create_recommendations(req: RecommendationRequest) -> RecommendationResponse:
    if req.preference not in PREFERENCE_OPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid preference '{req.preference}'. Allowed: {PREFERENCE_OPTIONS}",
        )

    model_ready, msg = check_model_ready()
    if not model_ready:
        raise HTTPException(status_code=503, detail=msg)

    try:
        df = prepare_dataset()
        model = load_model()

        if req.arrival_timestamp:
            try:
                target_dt = pd.to_datetime(req.arrival_timestamp)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid arrival_timestamp format.")
            records_df, resolved_dt = get_records_at_timestamp(df, target_dt)
            queried_ts_str = req.arrival_timestamp
        else:
            records_df = get_latest_records(df)
            resolved_dt = records_df["timestamp"].iloc[0]
            queried_ts_str = str(resolved_dt)

        scored = calculate_recommendation_scores(records_df, model, historical_df=df)
        top = get_top_recommendations(
            scored,
            preference=req.preference,
            top_n=3,
            parking_type_filter=req.parking_type,
        )

        recommendations: List[RecommendationItem] = []
        for _, r in top.iterrows():
            recommendations.append(
                RecommendationItem(
                    rank=int(r["rank"]),
                    parking_id=str(r["parking_id"]),
                    parking_name=str(r["parking_name"]),
                    parking_type=str(r["parking_type"]),
                    latitude=float(r["latitude"]),
                    longitude=float(r["longitude"]),
                    predicted_available_spaces=int(r["predicted_available_spaces"]),
                    total_spaces=int(r["total_spaces"]),
                    availability_pct=float(r["availability_pct"]),
                    availability_status=str(r["availability_status"]),
                    confidence=str(r["confidence"]),
                    distance_km=float(r["distance_km"]),
                    price_per_hour=float(r["price_per_hour"]),
                    recommendation_score=float(r["recommendation_score"]),
                    explanation=str(r["explanation"]),
                )
            )

        return RecommendationResponse(
            success=True,
            timestamp_queried=queried_ts_str,
            timestamp_resolved=str(resolved_dt),
            preference_applied=req.preference,
            recommendations=recommendations,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback", response_model=FeedbackResponse, summary="Submit actual observed parking status")
def submit_feedback(req: FeedbackRequest) -> FeedbackResponse:
    if req.actual_status not in FEEDBACK_STATUS_OPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{req.actual_status}'. Allowed: {FEEDBACK_STATUS_OPTIONS}",
        )
    try:
        save_feedback(
            parking_id=req.parking_id,
            actual_status=req.actual_status,
            comment=req.comment or "",
        )
        return FeedbackResponse(success=True, message="Feedback submitted successfully.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feedback", summary="View all stored user feedback")
def get_all_feedback() -> Dict[str, Any]:
    try:
        df_feed = load_feedback()
        return {"success": True, "count": len(df_feed), "feedback": df_feed.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
