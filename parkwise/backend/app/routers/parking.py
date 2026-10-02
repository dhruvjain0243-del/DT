from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..dependencies import CurrentUser, DbSession, require_roles
from ..models import EntryMethod, ParkingSession, ParkingSessionStatus, ScanResult, ScanType, User, UserRole, Vehicle
from ..schemas.common import MessageResponse
from ..schemas.parking import (
    ConfirmSlotRequest,
    ExitResponse,
    FindVehicleResponse,
    ParkingEntryRequest,
    ParkingExitRequest,
    ParkingManualExitRequest,
    ParkingSessionRead,
    TicketResponse,
)
from ..schemas.resources import SlotCorrectionRequest
from ..schemas.auth import normalize_registration
from ..services.audit import record_audit
from ..services.parking import (
    close_session,
    confirm_assigned_slot,
    correct_slot,
    create_entry,
    ensure_session_access,
    find_vehicle,
    get_session_by_ticket,
    ticket_response,
)
from ..services.qr import qr_png_bytes
from ..services.operations import record_scan_event, validate_scan_context


router = APIRouter(prefix="/api/parking", tags=["parking"])
StaffUser = Depends(require_roles(UserRole.ADMIN, UserRole.ATTENDANT))


@router.post("/entry", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def entry(data: ParkingEntryRequest, user: CurrentUser, db: DbSession) -> TicketResponse:
    try:
        _, scanner = validate_scan_context(
            db,
            facility_id=data.facility_id,
            gate_id=data.gate_id,
            scanner_device_id=data.scanner_device_id,
            scan_type=ScanType.ENTRY,
        )
        session = create_entry(db, data, user)
        record_audit(
            db,
            actor_user_id=user.id,
            action="PARKING_ENTRY",
            entity_type="parking_session",
            entity_id=session.id,
            details={"ticket_id": session.ticket_id},
        )
        if data.gate_id is not None:
            record_scan_event(
                db,
                facility_id=session.facility_id,
                gate_id=data.gate_id,
                scanner_device_id=scanner.id if scanner else None,
                actor_user_id=user.id,
                session_id=session.id,
                scan_type=ScanType.ENTRY,
                result=ScanResult.SUCCESS,
                reference=data.scan_reference or session.ticket_id,
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Vehicle or slot already has an active session") from exc
    return ticket_response(get_session_by_ticket(db, session.ticket_id))


@router.get("/session/{ticket_id}", response_model=TicketResponse)
def session_by_ticket(ticket_id: str, user: CurrentUser, db: DbSession) -> TicketResponse:
    session = get_session_by_ticket(db, ticket_id)
    ensure_session_access(user, session)
    return ticket_response(session)


@router.get("/session/{ticket_id}/qr.png")
def ticket_qr(ticket_id: str, user: CurrentUser, db: DbSession) -> Response:
    session = get_session_by_ticket(db, ticket_id)
    ensure_session_access(user, session)
    response = ticket_response(session)
    return Response(
        qr_png_bytes(response.qr_token),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="ticket-{ticket_id}.png"'},
    )


@router.get("/active", response_model=list[ParkingSessionRead])
def active_sessions(db: DbSession, staff: User = StaffUser) -> list[ParkingSession]:
    return list(
        db.scalars(
            select(ParkingSession)
            .where(ParkingSession.status == ParkingSessionStatus.ACTIVE)
            .order_by(ParkingSession.entry_time.desc())
        )
    )


@router.get("/my-active-session", response_model=TicketResponse)
def my_active_session(user: CurrentUser, db: DbSession) -> TicketResponse:
    session = db.scalar(
        select(ParkingSession).where(
            ParkingSession.user_id == user.id,
            ParkingSession.status == ParkingSessionStatus.ACTIVE,
        ).order_by(ParkingSession.entry_time.desc())
    )
    if not session:
        raise HTTPException(status_code=404, detail="No active parking session")
    return ticket_response(get_session_by_ticket(db, session.ticket_id))


@router.get("/my-history", response_model=list[ParkingSessionRead])
def my_history(user: CurrentUser, db: DbSession) -> list[ParkingSession]:
    return list(
        db.scalars(
            select(ParkingSession)
            .where(ParkingSession.user_id == user.id)
            .order_by(ParkingSession.entry_time.desc())
        )
    )


@router.post("/exit", response_model=ExitResponse)
def exit_parking(data: ParkingExitRequest, user: CurrentUser, db: DbSession) -> ExitResponse:
    try:
        session = get_session_by_ticket(db, data.ticket_id)
        ensure_session_access(user, session)
        _, scanner = validate_scan_context(
            db,
            facility_id=session.facility_id,
            gate_id=data.gate_id,
            scanner_device_id=data.scanner_device_id,
            scan_type=ScanType.EXIT,
        )
        result = close_session(
            db,
            ticket_id=data.ticket_id,
            requester=user,
            method=EntryMethod.QR,
            qr_token=data.qr_token,
        )
        record_audit(
            db,
            actor_user_id=user.id,
            action="PARKING_EXIT",
            entity_type="parking_session",
            entity_id=data.ticket_id,
        )
        if data.gate_id is not None:
            record_scan_event(
                db,
                facility_id=session.facility_id,
                gate_id=data.gate_id,
                scanner_device_id=scanner.id if scanner else None,
                actor_user_id=user.id,
                session_id=session.id,
                scan_type=ScanType.EXIT,
                result=ScanResult.SUCCESS,
                reference=data.scan_reference or data.ticket_id,
            )
        # Session completion, slot release, and its audit record commit atomically.
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


@router.post("/manual-exit", response_model=ExitResponse)
def manual_exit(data: ParkingManualExitRequest, db: DbSession, staff: User = StaffUser) -> ExitResponse:
    result = close_session(
        db, ticket_id=data.ticket_id, requester=staff, method=EntryMethod.MANUAL
    )
    record_audit(db, actor_user_id=staff.id, action="MANUAL_EXIT", entity_type="parking_session", entity_id=data.ticket_id)
    db.commit()
    return result


@router.get("/find-my-vehicle/{ticket_id}", response_model=FindVehicleResponse)
def locate_vehicle(ticket_id: str, user: CurrentUser, db: DbSession) -> FindVehicleResponse:
    return find_vehicle(db, ticket_id, user)


@router.post("/confirm-slot", response_model=MessageResponse)
def confirm_slot(data: ConfirmSlotRequest, user: CurrentUser, db: DbSession) -> MessageResponse:
    confirm_assigned_slot(db, data.ticket_id, data.slot_qr_token, user)
    return MessageResponse(message="Slot QR matches the active parking assignment")


@router.get("/recover", response_model=TicketResponse)
def recover_lost_ticket(
    registration_number: str, db: DbSession, staff: User = StaffUser
) -> TicketResponse:
    registration = normalize_registration(registration_number)
    session = db.scalar(
        select(ParkingSession)
        .join(Vehicle)
        .where(
            Vehicle.registration_number == registration,
            ParkingSession.status == ParkingSessionStatus.ACTIVE,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="No active ticket for this vehicle")
    record_audit(db, actor_user_id=staff.id, action="RECOVER_TICKET", entity_type="parking_session", entity_id=session.id)
    db.commit()
    return ticket_response(get_session_by_ticket(db, session.ticket_id))


@router.put("/session/{ticket_id}/slot", response_model=TicketResponse)
def fix_slot(
    ticket_id: str,
    data: SlotCorrectionRequest,
    db: DbSession,
    staff: User = StaffUser,
) -> TicketResponse:
    session = correct_slot(db, ticket_id, data.slot_id, staff)
    record_audit(
        db,
        actor_user_id=staff.id,
        action="CORRECT_SLOT",
        entity_type="parking_session",
        entity_id=session.id,
        details={"new_slot_id": data.slot_id},
    )
    db.commit()
    return ticket_response(get_session_by_ticket(db, ticket_id))
