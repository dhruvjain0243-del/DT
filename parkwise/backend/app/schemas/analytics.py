from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import FeedbackCategory, FeedbackStatus


class FeedbackCreate(BaseModel):
    session_id: int | None = Field(default=None, gt=0)
    category: FeedbackCategory
    description: str = Field(min_length=5, max_length=2000)
    reported_available_spaces: int | None = Field(default=None, ge=0)


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    session_id: int | None
    category: FeedbackCategory
    description: str
    reported_available_spaces: int | None
    status: FeedbackStatus
    created_at: datetime


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    facility_id: int
    zone_id: int | None
    prediction_time: datetime
    target_time: datetime
    predicted_available_spaces: int
    actual_available_spaces: int | None
    model_version: str
    created_at: datetime


class PredictionRunResponse(BaseModel):
    predictions: list[PredictionRead]
    model_available: bool
    model_version: str
    data_label: str = "Simulated-model estimate; not a real-time guarantee"


class ModelMetricsResponse(BaseModel):
    baseline_mae: float | None = None
    model_mae: float | None = None
    model_rmse: float | None = None
    model_r2: float | None = None
    train_rows: int | None = None
    test_rows: int | None = None
    dataset_type: str = "simulated"
    prediction_horizon_minutes: int = 30
