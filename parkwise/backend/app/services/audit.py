from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def record_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=json.dumps(details, default=str) if details else None,
    )
    db.add(log)
    return log
