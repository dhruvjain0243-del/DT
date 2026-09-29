from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..core.config import get_settings
from ..dependencies import CurrentUser, DbSession, require_roles
from ..models import Prediction, User, UserRole
from ..schemas.analytics import ModelMetricsResponse, PredictionRead, PredictionRunResponse
from ..services.audit import record_audit
from ..services.predictions import model_metrics, run_predictions


router = APIRouter(prefix="/api/predictions", tags=["predictions"])
AdminUser = Depends(require_roles(UserRole.ADMIN))


@router.get("/latest", response_model=list[PredictionRead])
def latest_predictions(user: CurrentUser, db: DbSession) -> list[Prediction]:
    rows = db.scalars(select(Prediction).order_by(Prediction.prediction_time.desc()).limit(100)).all()
    latest: dict[int, Prediction] = {}
    for row in rows:
        latest.setdefault(row.facility_id, row)
    return list(latest.values())


@router.get("/metrics", response_model=ModelMetricsResponse)
def metrics(user: CurrentUser) -> ModelMetricsResponse:
    return ModelMetricsResponse(**model_metrics())


@router.get("/{facility_id}", response_model=list[PredictionRead])
def facility_predictions(facility_id: int, user: CurrentUser, db: DbSession) -> list[Prediction]:
    return list(
        db.scalars(
            select(Prediction)
            .where(Prediction.facility_id == facility_id)
            .order_by(Prediction.prediction_time.desc())
            .limit(200)
        )
    )


@router.post("/run", response_model=PredictionRunResponse)
def execute_predictions(db: DbSession, admin: User = AdminUser) -> PredictionRunResponse:
    rows, available = run_predictions(db)
    record_audit(db, actor_user_id=admin.id, action="RUN_PREDICTIONS", entity_type="prediction", details={"count": len(rows)})
    db.commit()
    return PredictionRunResponse(
        predictions=[PredictionRead.model_validate(row) for row in rows],
        model_available=available,
        model_version=get_settings().model_version,
    )
