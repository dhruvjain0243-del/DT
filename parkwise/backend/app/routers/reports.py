from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from io import StringIO

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..dependencies import DbSession, require_roles
from ..models import ParkingSession, User, UserRole
from ..schemas.parking import ParkingSessionRead


router = APIRouter(prefix="/api/reports", tags=["reports"])
AdminUser = Depends(require_roles(UserRole.ADMIN))


def _sessions_since(db: DbSession, since: datetime) -> list[ParkingSession]:
    return list(
        db.scalars(
            select(ParkingSession)
            .options(joinedload(ParkingSession.facility), joinedload(ParkingSession.vehicle))
            .where(ParkingSession.entry_time >= since)
            .order_by(ParkingSession.entry_time.desc())
        )
    )


def _summarize(sessions: list[ParkingSession], period: str) -> list[dict]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"entries": 0, "exits": 0})
    for item in sessions:
        key = item.entry_time.strftime("%Y-%m-%d" if period == "daily" else "%G-W%V")
        buckets[key]["entries"] += 1
        if item.exit_time:
            buckets[key]["exits"] += 1
    return [{"period": key, **value} for key, value in sorted(buckets.items())]


@router.get("/daily")
def daily_report(db: DbSession, admin: User = AdminUser, days: int = 30) -> list[dict]:
    days = max(1, min(days, 366))
    return _summarize(_sessions_since(db, datetime.now(UTC) - timedelta(days=days)), "daily")


@router.get("/weekly")
def weekly_report(db: DbSession, admin: User = AdminUser, weeks: int = 12) -> list[dict]:
    weeks = max(1, min(weeks, 104))
    return _summarize(_sessions_since(db, datetime.now(UTC) - timedelta(weeks=weeks)), "weekly")


@router.get("/peak-hours")
def peak_hours(db: DbSession, admin: User = AdminUser, days: int = 90) -> list[dict]:
    sessions = _sessions_since(db, datetime.now(UTC) - timedelta(days=max(1, min(days, 366))))
    counts = Counter(item.entry_time.hour for item in sessions)
    return [{"hour": hour, "entries": counts.get(hour, 0)} for hour in range(24)]


@router.get("/sessions", response_model=list[ParkingSessionRead])
def historical_sessions(
    db: DbSession,
    admin: User = AdminUser,
    days: int = 90,
    limit: int = 500,
) -> list[ParkingSession]:
    since = datetime.now(UTC) - timedelta(days=max(1, min(days, 366)))
    limit = max(1, min(limit, 2000))
    return list(
        db.scalars(
            select(ParkingSession)
            .where(ParkingSession.entry_time >= since)
            .order_by(ParkingSession.entry_time.desc())
            .limit(limit)
        )
    )


@router.get("/export-csv")
def export_csv(db: DbSession, admin: User = AdminUser, days: int = 90) -> Response:
    sessions = _sessions_since(db, datetime.now(UTC) - timedelta(days=max(1, min(days, 366))))
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ticket_id", "facility", "vehicle", "entry_time", "exit_time", "status"])
    for item in sessions:
        writer.writerow(
            [
                item.ticket_id,
                item.facility.name,
                item.vehicle.registration_number,
                item.entry_time.isoformat(),
                item.exit_time.isoformat() if item.exit_time else "",
                item.status.value,
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="parkwise-report.csv"'},
    )
