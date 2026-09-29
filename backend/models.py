from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class DateRangeResponse(BaseModel):
    min_date: datetime
    max_date: datetime

class NearestTimestampRequest(BaseModel):
    target_datetime: datetime

class NearestTimestampResponse(BaseModel):
    resolved_datetime: datetime

class RecommendationRequest(BaseModel):
    target_datetime: datetime
    preference: str
    parking_type_filter: str = "All"
    top_n: int = 3
    horizon_minutes: int = 30

class RecommendationItem(BaseModel):
    rank: int
    parking_name: str
    parking_type: str
    total_spaces: int
    predicted_available_spaces: int
    occupancy_rate: float
    availability_status: str
    availability_pct: float
    distance_km: float
    price_per_hour: float
    recommendation_score: float
    confidence: str
    explanation: str

class RecommendationResponse(BaseModel):
    resolved_datetime: datetime
    recommendations: List[RecommendationItem]
    total_evaluated: int
    model_mae: float

class FeedbackRequest(BaseModel):
    parking_name: str
    timestamp: datetime
    actual_status: str
    user_comment: Optional[str] = None
