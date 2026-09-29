from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..dependencies import DbSession, require_roles
from ..models import AuditLog, User, UserRole
from ..schemas.auth import UserAdminUpdate, UserRead
from ..schemas.common import MessageResponse
from ..services.audit import record_audit


router = APIRouter(prefix="/api", tags=["administration"])
AdminUser = Depends(require_roles(UserRole.ADMIN))


@router.get("/users", response_model=list[UserRead])
def list_users(db: DbSession, admin: User = AdminUser) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


@router.put("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: UserAdminUpdate, db: DbSession, admin: User = AdminUser) -> User:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and data.is_active is False:
        raise HTTPException(status_code=400, detail="Administrators cannot deactivate themselves")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(target, key, value)
    record_audit(db, actor_user_id=admin.id, action="UPDATE", entity_type="user", entity_id=target.id)
    db.commit()
    db.refresh(target)
    return target


@router.get("/audit-logs")
def audit_logs(db: DbSession, admin: User = AdminUser, limit: int = 200) -> list[dict]:
    limit = max(1, min(limit, 1000))
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "actor_user_id": row.actor_user_id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]
