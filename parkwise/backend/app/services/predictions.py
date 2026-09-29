from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import Facility, ParkingSession, ParkingSessionStatus, Prediction


logger = logging.getLogger(__name__)


@lru_cache
def load_model_bundle() -> tuple[Any | None, list[str], dict[str, Any]]:
    settings = get_settings()
    metrics: dict[str, Any] = {}
    if settings.model_metrics_path.exists():
        metrics = json.loads(settings.model_metrics_path.read_text(encoding="utf-8"))
    features = [
        "hour",
        "minute",
        "day_of_week",
        "is_weekend",
        "is_peak_hour",
        "total_spaces",
        "occupied_spaces",
        "distance_km",
        "price_per_hour",
        "event_flag",
    ]
    if settings.model_feature_columns_path.exists():
        features = json.loads(
            settings.model_feature_columns_path.read_text(encoding="utf-8")
        )
    path = Path(settings.model_path).resolve()
    if not path.is_file():
        logger.warning("Prediction model is unavailable; deterministic fallback enabled")
        return None, features, metrics
    if settings.ml_model_sha256:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest.lower() != settings.ml_model_sha256.lower():
            logger.error("Prediction model checksum mismatch; refusing to deserialize")
            return None, features, metrics
    try:
        # joblib/pickle files are executable data. Only the trusted, configured local
        # artifact is loaded; production deployments should set ML_MODEL_SHA256.
        model = joblib.load(path)
    except Exception:
        logger.exception("Prediction model could not be loaded; using fallback")
        return None, features, metrics
    return model, features, metrics


def model_metrics() -> dict[str, Any]:
    return load_model_bundle()[2]


def run_predictions(db: Session) -> tuple[list[Prediction], bool]:
    settings = get_settings()
    model, features, _ = load_model_bundle()
    now = datetime.now(UTC)

    due_predictions = db.scalars(
        select(Prediction).where(
            Prediction.target_time <= now,
            Prediction.actual_available_spaces.is_(None),
        )
    ).all()
    for previous in due_predictions:
        occupied = int(
            db.scalar(
                select(func.count(ParkingSession.id)).where(
                    ParkingSession.facility_id == previous.facility_id,
                    ParkingSession.status == ParkingSessionStatus.ACTIVE,
                )
            )
            or 0
        )
        facility = db.get(Facility, previous.facility_id)
        if facility:
            previous.actual_available_spaces = max(0, facility.total_capacity - occupied)

    results: list[Prediction] = []
    facilities = db.scalars(
        select(Facility).where(Facility.is_active.is_(True)).order_by(Facility.id)
    ).all()
    for facility in facilities:
        occupied = int(
            db.scalar(
                select(func.count(ParkingSession.id)).where(
                    ParkingSession.facility_id == facility.id,
                    ParkingSession.status == ParkingSessionStatus.ACTIVE,
                )
            )
            or 0
        )
        row = {
            "hour": now.hour,
            "minute": now.minute,
            "day_of_week": now.weekday(),
            "is_weekend": int(now.weekday() >= 5),
            "is_peak_hour": int(now.hour in {8, 9, 17, 18}),
            "total_spaces": facility.total_capacity,
            "occupied_spaces": occupied,
            "distance_km": facility.distance_km,
            "price_per_hour": facility.price_per_hour,
            "event_flag": 0,
        }
        fallback = max(0, facility.total_capacity - occupied)
        try:
            raw = float(model.predict(pd.DataFrame([row], columns=features))[0]) if model else fallback
        except Exception:
            logger.exception("Model inference failed for facility %s", facility.id)
            raw = fallback
        predicted = max(0, min(facility.total_capacity, round(raw)))
        prediction = Prediction(
            facility_id=facility.id,
            zone_id=None,
            prediction_time=now,
            target_time=now + timedelta(minutes=30),
            predicted_available_spaces=predicted,
            model_version=settings.model_version if model else f"{settings.model_version}-fallback",
        )
        db.add(prediction)
        results.append(prediction)
    db.flush()
    return results, model is not None
