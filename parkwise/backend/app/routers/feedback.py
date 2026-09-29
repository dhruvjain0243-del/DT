from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ..dependencies import CurrentUser, DbSession, require_roles
from ..models import Feedback, ParkingSession, User, UserRole
from ..schemas.analytics import FeedbackCreate, FeedbackRead, FeedbackStatusUpdate
from ..services.audit import record_audit


router = APIRouter(prefix="/api/feedback", tags=["feedback"])
AdminUser = Depends(require_roles(UserRole.ADMIN))


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(data: FeedbackCreate, user: CurrentUser, db: DbSession) -> Feedback:
    if data.session_id:
        session = db.get(ParkingSession, data.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Parking session not found")
        if session.user_id != user.id and user.role not in {UserRole.ADMIN, UserRole.ATTENDANT}:
            raise HTTPException(status_code=403, detail="Cannot comment on another user's session")
    feedback = Feedback(user_id=user.id, **data.model_dump())
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("", response_model=list[FeedbackRead])
def list_feedback(db: DbSession, admin: User = AdminUser) -> list[Feedback]:
    return list(db.scalars(select(Feedback).order_by(Feedback.created_at.desc())))


@router.put("/{feedback_id}/status", response_model=FeedbackRead)
def update_feedback_status(
    feedback_id: int,
    data: FeedbackStatusUpdate,
    db: DbSession,
    admin: User = AdminUser,
) -> Feedback:
    feedback = db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    feedback.status = data.status
    record_audit(db, actor_user_id=admin.id, action="UPDATE_STATUS", entity_type="feedback", entity_id=feedback.id)
    db.commit()
    db.refresh(feedback)
    return feedback
