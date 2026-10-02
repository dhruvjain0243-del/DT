from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..dependencies import CurrentUser, DbSession, require_roles
from ..models import Facility, ParkingGate, ParkingSession, ScanEvent, ScanResult, ScanType, ScannerDevice, User, UserRole, Vehicle
from ..schemas.operations import GateCreate, GateRead, ScanEventRead, ScannerActionResponse, ScannerCreate, ScannerProvisioned, ScannerRead, ScannerScanRequest
from ..schemas.parking import ParkingEntryRequest, ParkingExitRequest
from ..core.security import TokenError, decode_token
from ..services.operations import authenticate_scanner, provision_scanner_key, record_scan_event, rotate_scanner_key, validate_scan_context
from ..services.parking import close_session, create_entry, get_session_by_ticket, ticket_response
from ..services.audit import record_audit


router = APIRouter(prefix="/api/operations", tags=["operations"])
AdminUser = Depends(require_roles(UserRole.ADMIN))
StaffUser = Depends(require_roles(UserRole.ADMIN, UserRole.ATTENDANT))


@router.post("/facilities/{facility_id}/gates", response_model=GateRead, status_code=status.HTTP_201_CREATED)
def create_gate(facility_id: int, data: GateCreate, db: DbSession, admin: User = AdminUser) -> ParkingGate:
    facility = db.get(Facility, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    gate = ParkingGate(facility_id=facility_id, **data.model_dump())
    db.add(gate)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A gate with this name already exists in the facility") from exc
    record_audit(db, actor_user_id=admin.id, action="CREATE_GATE", entity_type="parking_gate", entity_id=gate.id)
    db.commit()
    db.refresh(gate)
    return gate


@router.get("/facilities/{facility_id}/gates", response_model=list[GateRead])
def list_gates(facility_id: int, db: DbSession, user: CurrentUser) -> list[ParkingGate]:
    if not db.get(Facility, facility_id):
        raise HTTPException(status_code=404, detail="Facility not found")
    return list(db.scalars(select(ParkingGate).where(ParkingGate.facility_id == facility_id).order_by(ParkingGate.name)))


@router.post("/gates/{gate_id}/scanners", response_model=ScannerProvisioned, status_code=status.HTTP_201_CREATED)
def create_scanner(gate_id: int, data: ScannerCreate, db: DbSession, admin: User = AdminUser) -> dict:
    gate = db.get(ParkingGate, gate_id)
    if not gate:
        raise HTTPException(status_code=404, detail="Gate not found")
    api_key, api_key_hash = provision_scanner_key()
    scanner = ScannerDevice(gate_id=gate_id, api_key_hash=api_key_hash, **data.model_dump())
    db.add(scanner)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A scanner with this device identifier already exists") from exc
    record_audit(db, actor_user_id=admin.id, action="CREATE_SCANNER", entity_type="scanner_device", entity_id=scanner.id)
    db.commit()
    db.refresh(scanner)
    return {**ScannerRead.model_validate(scanner).model_dump(), "api_key": api_key}


@router.post("/scanners/{scanner_id}/scan", response_model=dict)
def scanner_scan(
    scanner_id: int,
    data: ScannerScanRequest,
    db: DbSession,
    x_scanner_key: str | None = Header(default=None),
) -> dict:
    scanner = authenticate_scanner(db, scanner_id, x_scanner_key or "")
    gate = db.get(ParkingGate, scanner.gate_id)
    if not gate:
        raise HTTPException(status_code=404, detail="Scanner gate not found")
    validate_scan_context(db, facility_id=gate.facility_id, gate_id=gate.id, scanner_device_id=scanner.id, scan_type=data.scan_type)

    if data.scan_type == ScanType.ENTRY:
        if not data.vehicle_registration:
            raise HTTPException(status_code=400, detail="Vehicle registration is required for entry scans")
        vehicle = db.scalar(select(Vehicle).where(Vehicle.registration_number == data.vehicle_registration.upper()))
        if not vehicle:
            raise HTTPException(status_code=404, detail="Registered vehicle not found")
        session = create_entry(db, ParkingEntryRequest(vehicle_id=vehicle.id, facility_id=gate.facility_id), vehicle.user)
        record_scan_event(db, facility_id=gate.facility_id, gate_id=gate.id, scanner_device_id=scanner.id, actor_user_id=vehicle.user_id, session_id=session.id, scan_type=data.scan_type, result=ScanResult.SUCCESS, reference=data.scan_reference or session.ticket_id)
        db.commit()
        return {"scan_type": data.scan_type, "result": ScanResult.SUCCESS, "ticket": ticket_response(get_session_by_ticket(db, session.ticket_id)).model_dump()}

    if not data.qr_token:
        raise HTTPException(status_code=400, detail="Ticket QR token is required for exit scans")
    try:
        payload = decode_token(data.qr_token, "ticket_qr")
        ticket_id = str(payload["ref"])
    except (TokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid ticket QR token") from exc
    session = get_session_by_ticket(db, ticket_id)
    result = close_session(db, ticket_id=ticket_id, requester=session.user, method="QR", qr_token=data.qr_token)
    record_scan_event(db, facility_id=gate.facility_id, gate_id=gate.id, scanner_device_id=scanner.id, actor_user_id=session.user_id, session_id=session.id, scan_type=data.scan_type, result=ScanResult.SUCCESS, reference=data.scan_reference or ticket_id)
    db.commit()
    return {"scan_type": data.scan_type, "result": ScanResult.SUCCESS, "exit": result.model_dump()}


@router.get("/gates/{gate_id}/scanners", response_model=list[ScannerRead])
def list_scanners(gate_id: int, db: DbSession, user: CurrentUser) -> list[ScannerDevice]:
    if not db.get(ParkingGate, gate_id):
        raise HTTPException(status_code=404, detail="Gate not found")
    return list(db.scalars(select(ScannerDevice).where(ScannerDevice.gate_id == gate_id).order_by(ScannerDevice.name)))


@router.post("/scanners/{scanner_id}/revoke", response_model=ScannerActionResponse)
def revoke_scanner(scanner_id: int, db: DbSession, admin: User = AdminUser) -> dict:
    scanner = db.get(ScannerDevice, scanner_id)
    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner not found")
    scanner.is_active = False
    scanner.api_key_hash = None
    record_audit(db, actor_user_id=admin.id, action="REVOKE_SCANNER", entity_type="scanner_device", entity_id=scanner.id)
    db.commit()
    db.refresh(scanner)
    return {**ScannerRead.model_validate(scanner).model_dump(), "message": "Scanner key revoked"}


@router.post("/scanners/{scanner_id}/regenerate", response_model=ScannerProvisioned)
def regenerate_scanner(scanner_id: int, db: DbSession, admin: User = AdminUser) -> dict:
    scanner = db.get(ScannerDevice, scanner_id)
    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner not found")
    api_key = rotate_scanner_key(scanner)
    record_audit(db, actor_user_id=admin.id, action="REGENERATE_SCANNER_KEY", entity_type="scanner_device", entity_id=scanner.id)
    db.commit()
    db.refresh(scanner)
    return {**ScannerRead.model_validate(scanner).model_dump(), "api_key": api_key}


@router.get("/scan-events", response_model=list[ScanEventRead])
def list_scan_events(
    db: DbSession,
    staff: User = StaffUser,
    facility_id: int | None = Query(default=None, gt=0),
    result: ScanResult | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ScanEvent]:
    query = select(ScanEvent).order_by(ScanEvent.scanned_at.desc()).limit(limit)
    if facility_id:
        query = query.where(ScanEvent.facility_id == facility_id)
    if result:
        query = query.where(ScanEvent.result == result)
    return list(db.scalars(query))
