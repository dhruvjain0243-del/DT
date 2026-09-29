from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
import pandas as pd

# Import from backend modules
from backend.models import (
    DateRangeResponse, NearestTimestampRequest, NearestTimestampResponse,
    RecommendationRequest, RecommendationResponse, RecommendationItem,
    FeedbackRequest, TokenResponse
)
from backend.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, verify_password,
    get_current_user, USERS
)
from backend.data_service import prepare_dataset, get_available_date_range, get_records_at_timestamp
from backend.model_service import load_model, check_model_ready, load_metrics
from backend.recommendation_service import calculate_recommendation_scores, get_top_recommendations
from backend.feedback_service import save_feedback

app = FastAPI(title="ParkWise API", description="Smart Parking Recommendation System")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global data and model variables
df_raw = None
ml_model = None
metrics = None

@app.on_event("startup")
def load_resources():
    global df_raw, ml_model, metrics
    try:
        df_raw = prepare_dataset()
    except Exception as e:
        print(f"Error loading dataset: {e}")
    
    model_ready, _ = check_model_ready()
    if model_ready:
        try:
            ml_model = load_model()
            metrics = load_metrics()
        except Exception as e:
            print(f"Error loading model: {e}")

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/available-dates", response_model=DateRangeResponse)
def get_dates(current_user: dict = Depends(get_current_user)):
    if df_raw is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded")
    min_ts, max_ts = get_available_date_range(df_raw)
    return {"min_date": min_ts, "max_date": max_ts}

@app.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(req: RecommendationRequest, current_user: dict = Depends(get_current_user)):
    if df_raw is None or ml_model is None:
        raise HTTPException(status_code=500, detail="System not ready")
        
    records_df, resolved_dt = get_records_at_timestamp(df_raw, pd.to_datetime(req.target_datetime))
    
    scored_df = calculate_recommendation_scores(records_df, ml_model, historical_df=df_raw)
    top_recs = get_top_recommendations(
        scored_df,
        preference=req.preference,
        top_n=req.top_n,
        parking_type_filter=req.parking_type_filter,
    )
    
    recs = []
    for idx, row in top_recs.iterrows():
        recs.append(RecommendationItem(
            rank=row['rank'],
            parking_name=row['parking_name'],
            parking_type=row['parking_type'],
            total_spaces=row['total_spaces'],
            predicted_available_spaces=row['predicted_available_spaces'],
            occupancy_rate=row['occupancy_rate'],
            availability_status=row['availability_status'],
            availability_pct=row['availability_pct'],
            distance_km=row['distance_km'],
            price_per_hour=row['price_per_hour'],
            recommendation_score=row['recommendation_score'],
            confidence=row['confidence'],
            explanation=row['explanation']
        ))
        
    return {
        "resolved_datetime": resolved_dt,
        "recommendations": recs,
        "total_evaluated": len(scored_df),
        "model_mae": metrics.get("model_mae", 0.0) if metrics else 0.0
    }

@app.get("/history")
def get_history(parking_name: str, current_user: dict = Depends(get_current_user)):
    if df_raw is None:
        raise HTTPException(status_code=500, detail="Dataset not loaded")
    
    hist_df = df_raw[df_raw["parking_name"] == parking_name].sort_values("timestamp")
    
    # Take latest 300 data points to prevent giant payload
    hist_df = hist_df.tail(300)
    
    data = []
    for _, row in hist_df.iterrows():
        data.append({
            "timestamp": row["timestamp"].isoformat(),
            "occupancy_rate": row["occupancy_rate"],
            "available_spaces": row["available_spaces"],
            "hour": row["hour"] if "hour" in row else row["timestamp"].hour
        })
    return data

@app.post("/feedback")
def submit_feedback(req: FeedbackRequest, current_user: dict = Depends(get_current_user)):
    try:
        save_feedback(
            parking_name=req.parking_name,
            timestamp=req.timestamp,
            actual_status=req.actual_status,
            user_comment=req.user_comment
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
