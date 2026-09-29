from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..core.security import TokenError, create_qr_token, decode_token
from ..models import (
    EntryMethod,
    Facility,
    ParkingSession,
    ParkingSessionStatus,
    ParkingSlot,
    ParkingZone,
    SlotStatus,
    User,
    UserRole,
    Vehicle,
)
from ..schemas.parking import (
    ExitResponse,
    FindVehicleResponse,
    ParkingEntryRequest,
    TicketResponse,
)
from .qr import qr_png_base64


PRIVILEGED_ROLES = {UserRole.ADMIN, UserRole.ATTENDANT}


def _session_query():
    return select(ParkingSession).options(
        joinedload(ParkingSession.user),
        joinedload(ParkingSession.vehicle),
        joinedload(ParkingSession.facility),
        joinedload(ParkingSession.zone),
        joinedload(ParkingSession.slot),
    )


def get_session_by_ticket(db: Session, ticket_id: str) -> ParkingSession:
    session = db.scalar(_session_query().where(ParkingSession.ticket_id == ticket_id))
    if not session:
        raise HTTPException(status_code=404, detail="Parking ticket not found")
    return session


def ensure_session_access(requester: User, session: ParkingSession) -> None:
    if requester.role not in PRIVILEGED_ROLES and requester.id != session.user_id:
        raise HTTPException(status_code=403, detail="This ticket belongs to another user")


def ticket_response(session: ParkingSession) -> TicketResponse:
    token = create_qr_token(session.ticket_id, "ticket_qr")
    return TicketResponse(
        **{
            column: getattr(session, column)
            for column in (
                "id",
                "ticket_id",
                "user_id",
                "vehicle_id",
                "facility_id",
                "zone_id",
                "slot_id",
                "entry_time",
                "exit_time",
                "status",
                "entry_method",
                "exit_method",
                "created_at",
            )
        },
        facility_name=session.facility.name,
        zone_name=session.zone.name,
        row_label=session.slot.row_label,
        slot_code=session.slot.slot_code,
        registration_number=session.vehicle.registration_number,
        qr_token=token,
        qr_png_base64=qr_png_base64(token),
    )


def create_entry(
    db: Session, request: ParkingEntryRequest, requester: User
) -> ParkingSession:
    scanned_slot_id: int | None = None
    if request.entry_method == EntryMethod.QR:
        if not request.slot_qr_token:
            raise HTTPException(status_code=400, detail="A slot QR token is required for QR entry")
        try:
            payload = decode_token(request.slot_qr_token, "slot_qr")
            scanned_slot_id = int(payload["ref"])
        except (TokenError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid or expired slot QR code") from exc
        if request.slot_id is not None and request.slot_id != scanned_slot_id:
            raise HTTPException(status_code=400, detail="Scanned slot does not match the requested slot")

    vehicle = db.scalar(
        select(Vehicle).where(Vehicle.id == request.vehicle_id).with_for_update()
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    target_user_id = request.user_id or vehicle.user_id
    if requester.role not in PRIVILEGED_ROLES and target_user_id != requester.id:
        raise HTTPException(status_code=403, detail="Cannot create a session for another user")
    if vehicle.user_id != target_user_id:
        raise HTTPException(status_code=400, detail="Vehicle does not belong to the selected user")

    facility = db.scalar(
        select(Facility).where(Facility.id == request.facility_id).with_for_update()
    )
    if not facility or not facility.is_active:
        raise HTTPException(status_code=404, detail="Active facility not found")

    duplicate = db.scalar(
        select(ParkingSession.id).where(
            ParkingSession.vehicle_id == vehicle.id,
            ParkingSession.status == ParkingSessionStatus.ACTIVE,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Vehicle already has an active session")

    active_count = len(
        db.scalars(
            select(ParkingSession.id).where(
                ParkingSession.facility_id == facility.id,
                ParkingSession.status == ParkingSessionStatus.ACTIVE,
            )
        ).all()
    )
    if active_count >= facility.total_capacity:
        raise HTTPException(status_code=409, detail="Parking facility is full")

    slot_query = (
        select(ParkingSlot)
        .join(ParkingZone)
        .where(
            ParkingZone.facility_id == facility.id,
            ParkingZone.vehicle_type == vehicle.vehicle_type,
            ParkingZone.is_active.is_(True),
            ParkingSlot.status == SlotStatus.AVAILABLE,
            ParkingSlot.is_active.is_(True),
        )
        .order_by(ParkingZone.name, ParkingSlot.row_label, ParkingSlot.slot_code)
        .with_for_update()
    )
    if request.zone_id:
        slot_query = slot_query.where(ParkingZone.id == request.zone_id)
    slot_id = scanned_slot_id or request.slot_id
    if slot_id:
        slot_query = slot_query.where(ParkingSlot.id == slot_id)
    slot = db.scalar(slot_query.limit(1))
    if not slot:
        raise HTTPException(
            status_code=409,
            detail="No suitable available slot exists for this vehicle type",
        )

    ticket_id = f"PW-{uuid4().hex.upper()}"
    parking_session = ParkingSession(
        ticket_id=ticket_id,
        user_id=target_user_id,
        vehicle_id=vehicle.id,
        facility_id=facility.id,
        zone_id=slot.zone_id,
        slot_id=slot.id,
        status=ParkingSessionStatus.ACTIVE,
        entry_method=request.entry_method,
    )
    slot.status = SlotStatus.OCCUPIED
    db.add(parking_session)
    db.flush()
    db.refresh(parking_session)
    return get_session_by_ticket(db, ticket_id)


def close_session(
    db: Session,
    *,
    ticket_id: str,
    requester: User,
    method: EntryMethod,
    qr_token: str | None = None,
) -> ExitResponse:
    session = db.scalar(
        _session_query().where(ParkingSession.ticket_id == ticket_id).with_for_update()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Parking ticket not found")
    ensure_session_access(requester, session)
    if session.status != ParkingSessionStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Parking session has already been closed")
    if method != EntryMethod.MANUAL:
        if not qr_token:
            raise HTTPException(status_code=400, detail="A ticket QR token is required")
        try:
            payload = decode_token(qr_token, "ticket_qr")
        except TokenError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload.get("ref") != ticket_id:
            raise HTTPException(status_code=400, detail="QR token does not match this ticket")

    slot = db.scalar(
        select(ParkingSlot).where(ParkingSlot.id == session.slot_id).with_for_update()
    )
    if not slot:
        raise HTTPException(status_code=409, detail="Assigned parking slot could not be found")
    now = datetime.now(UTC)
    session.status = ParkingSessionStatus.COMPLETED
    session.exit_time = now
    session.exit_method = method
    slot.status = SlotStatus.AVAILABLE
    db.flush()
    entry_time = session.entry_time
    if entry_time.tzinfo is None:
        entry_time = entry_time.replace(tzinfo=UTC)
    duration = max(0, int((now - entry_time).total_seconds() // 60))
    return ExitResponse(
        ticket_id=session.ticket_id,
        status=session.status,
        registration_number=session.vehicle.registration_number,
        vehicle_type=session.vehicle.vehicle_type,
        slot_id=slot.id,
        slot_code=slot.slot_code,
        entry_time=entry_time,
        exit_time=now,
        duration_minutes=duration,
        message="Vehicle exit recorded successfully",
    )


def find_vehicle(
    db: Session, ticket_id: str, requester: User
) -> FindVehicleResponse:
    session = get_session_by_ticket(db, ticket_id)
    ensure_session_access(requester, session)
    return FindVehicleResponse(
        ticket_id=session.ticket_id,
        status=session.status,
        facility_id=session.facility_id,
        facility_name=session.facility.name,
        facility_address=session.facility.address,
        latitude=session.facility.latitude,
        longitude=session.facility.longitude,
        zone_id=session.zone_id,
        zone_name=session.zone.name,
        row_label=session.slot.row_label,
        slot_id=session.slot_id,
        slot_code=session.slot.slot_code,
        entry_time=session.entry_time,
    )


def confirm_assigned_slot(
    db: Session, ticket_id: str, slot_qr_token: str, requester: User
) -> ParkingSession:
    session = get_session_by_ticket(db, ticket_id)
    ensure_session_access(requester, session)
    if session.status != ParkingSessionStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Parking session is no longer active")
    try:
        payload = decode_token(slot_qr_token, "slot_qr")
        scanned_slot_id = int(payload["ref"])
    except (TokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired slot QR code") from exc
    if scanned_slot_id != session.slot_id:
        raise HTTPException(status_code=409, detail="Scanned slot does not match the assigned slot")
    return session


def correct_slot(
    db: Session, ticket_id: str, new_slot_id: int, requester: User
) -> ParkingSession:
    if requester.role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    session = db.scalar(
        _session_query().where(ParkingSession.ticket_id == ticket_id).with_for_update()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Parking ticket not found")
    if session.status != ParkingSessionStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="Only active sessions can be corrected")
    new_slot = db.scalar(
        select(ParkingSlot)
        .options(joinedload(ParkingSlot.zone))
        .where(ParkingSlot.id == new_slot_id)
        .with_for_update()
    )
    if not new_slot or not new_slot.is_active:
        raise HTTPException(status_code=404, detail="Active destination slot not found")
    if new_slot.status != SlotStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail="Destination slot is not available")
    if new_slot.zone.facility_id != session.facility_id:
        raise HTTPException(status_code=400, detail="Destination slot belongs to another facility")
    if new_slot.zone.vehicle_type != session.vehicle.vehicle_type:
        raise HTTPException(status_code=400, detail="Destination slot has the wrong vehicle type")
    old_slot = db.get(ParkingSlot, session.slot_id)
    if old_slot:
        old_slot.status = SlotStatus.AVAILABLE
    new_slot.status = SlotStatus.OCCUPIED
    session.slot_id = new_slot.id
    session.zone_id = new_slot.zone_id
    db.flush()
    return get_session_by_ticket(db, ticket_id)
