from __future__ import annotations

import csv
from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from io import StringIO

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..dependencies import DbSession, require_roles
from ..models import ParkingSession, ScanEvent, ScanResult, User, UserRole
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


def _xlsx_bytes(sheets: dict[str, list[list[object]]]) -> bytes:
    """Create a small standards-compliant XLSX without exposing a new runtime dependency."""
    def cell(value: object) -> str:
        text = escape("" if value is None else str(value))
        return f'<c t="inlineStr"><is><t>{text}</t></is></c>'

    workbook_sheets = []
    sheet_rels = []
    content_overrides = []
    for index, name in enumerate(sheets, start=1):
        workbook_sheets.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
        sheet_rels.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
        content_overrides.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    files: dict[str, str] = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml">' + "</Override>" + "".join(content_overrides) + "</Types>",
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{"".join(workbook_sheets)}</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(sheet_rels)}</Relationships>',
    }
    for index, rows in enumerate(sheets.values(), start=1):
        xml_rows = "".join(f'<row>{"".join(cell(value) for value in row)}</row>' for row in rows)
        files[f"xl/worksheets/sheet{index}.xml"] = f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{xml_rows}</sheetData></worksheet>'
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


@router.get("/scanner-summary")
def scanner_summary(db: DbSession, admin: User = AdminUser, days: int = 30) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=max(1, min(days, 366)))
    events = list(db.scalars(select(ScanEvent).where(ScanEvent.scanned_at >= since).order_by(ScanEvent.scanned_at.desc())))
    buckets: dict[tuple[int, str], dict[str, int]] = {}
    for event in events:
        key = (event.scanner_device_id or 0, event.scanned_at.strftime("%Y-%m-%d"))
        bucket = buckets.setdefault(key, {"scanner_device_id": key[0], "day": key[1], "success": 0, "failed": 0, "entries": 0, "exits": 0})
        bucket["success" if event.result == ScanResult.SUCCESS else "failed"] += 1
        bucket["entries" if event.scan_type.value == "ENTRY" else "exits"] += 1
    return list(buckets.values())


@router.get("/export-xlsx")
def export_xlsx(db: DbSession, admin: User = AdminUser, days: int = 90) -> Response:
    since = datetime.now(UTC) - timedelta(days=max(1, min(days, 366)))
    sessions = _sessions_since(db, since)
    events = list(db.scalars(select(ScanEvent).where(ScanEvent.scanned_at >= since).order_by(ScanEvent.scanned_at.desc())))
    workbook = _xlsx_bytes({
        "Sessions": [["ticket_id", "facility", "vehicle", "entry_time", "exit_time", "status"]] + [[item.ticket_id, item.facility.name, item.vehicle.registration_number, item.entry_time.isoformat(), item.exit_time.isoformat() if item.exit_time else "", item.status.value] for item in sessions],
        "Scan events": [["scanned_at", "scanner_device_id", "gate_id", "scan_type", "result", "reference", "failure_reason"]] + [[event.scanned_at.isoformat(), event.scanner_device_id or "", event.gate_id, event.scan_type.value, event.result.value, event.reference or "", event.failure_reason or ""] for event in events],
    })
    return Response(workbook, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="parkwise-report.xlsx"'})
