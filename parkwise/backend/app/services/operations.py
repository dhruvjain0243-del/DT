from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_urlsafe

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.security import hash_password, verify_password
from ..models import ParkingGate, ScanEvent, ScanResult, ScanType, ScannerDevice


def provision_scanner_key() -> tuple[str, str]:
    raw_key = f"pwsc_{token_urlsafe(32)}"
    return raw_key, hash_password(raw_key)


def rotate_scanner_key(scanner: ScannerDevice) -> str:
    raw_key, scanner.api_key_hash = provision_scanner_key()
    scanner.is_active = True
    return raw_key


def authenticate_scanner(db: Session, scanner_id: int, api_key: str) -> ScannerDevice:
    scanner = db.get(ScannerDevice, scanner_id)
    if not scanner or not scanner.is_active or not scanner.api_key_hash or not verify_password(api_key, scanner.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid or inactive scanner credentials")
    return scanner


def validate_scan_context(
    db: Session,
    *,
    facility_id: int,
    gate_id: int | None,
    scanner_device_id: int | None,
    scan_type: ScanType,
) -> tuple[ParkingGate | None, ScannerDevice | None]:
    if gate_id is None and scanner_device_id is None:
        return None, None
    if gate_id is None and scanner_device_id is not None:
        raise HTTPException(status_code=400, detail="A gate is required when a scanner is supplied")

    gate = db.get(ParkingGate, gate_id)
    if not gate or gate.facility_id != facility_id:
        raise HTTPException(status_code=404, detail="Gate not found for this facility")
    if not gate.is_active:
        raise HTTPException(status_code=409, detail="Gate is inactive")
    if scan_type == ScanType.ENTRY and gate.gate_type.value not in {"ENTRY", "BOTH"}:
        raise HTTPException(status_code=409, detail="Gate is not configured for entry scans")
    if scan_type == ScanType.EXIT and gate.gate_type.value not in {"EXIT", "BOTH"}:
        raise HTTPException(status_code=409, detail="Gate is not configured for exit scans")

    scanner = None
    if scanner_device_id is not None:
        scanner = db.get(ScannerDevice, scanner_device_id)
        if not scanner or scanner.gate_id != gate.id:
            raise HTTPException(status_code=404, detail="Scanner is not assigned to this gate")
        if not scanner.is_active:
            raise HTTPException(status_code=409, detail="Scanner is inactive")
        scanner.last_seen_at = datetime.now(UTC)
    return gate, scanner


def record_scan_event(
    db: Session,
    *,
    facility_id: int,
    gate_id: int,
    scanner_device_id: int | None,
    actor_user_id: int | None,
    session_id: int | None,
    scan_type: ScanType,
    result: ScanResult,
    reference: str | None = None,
    failure_reason: str | None = None,
) -> ScanEvent:
    event = ScanEvent(
        facility_id=facility_id,
        gate_id=gate_id,
        scanner_device_id=scanner_device_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        scan_type=scan_type,
        result=result,
        reference=reference,
        failure_reason=failure_reason,
    )
    db.add(event)
    db.flush()
    return event
