from __future__ import annotations

from datetime import UTC, date, datetime, time
from io import BytesIO
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..core.config import get_settings
from ..dependencies import CurrentUser, DbSession, require_roles
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
    VehicleType,
)
from ..schemas.college import (
    CollegeActionResponse,
    CollegeConfigUpdate,
    CollegeFacilityRead,
    CollegeProfileRead,
    CollegeProfileUpdate,
    CollegeQrRead,
    CollegeSessionRead,
    CollegeSlotRead,
    AdminManualEntry,
    AdminManualExit,
)
from ..services.audit import record_audit
from ..services.parking import close_session, create_entry, get_session_by_ticket, ticket_response
from ..schemas.parking import ParkingEntryRequest
from ..services.qr import qr_png_bytes


router = APIRouter(prefix="/api/college", tags=["college parking"])
AdminUser = Depends(require_roles(UserRole.ADMIN))


def _facility(db: DbSession, facility_id: int | None = None) -> Facility:
    query = select(Facility).where(Facility.is_active.is_(True))
    if facility_id is not None:
        query = query.where(Facility.id == facility_id)
    facility = db.scalar(query.order_by(Facility.id.desc()))
    if not facility:
        raise HTTPException(status_code=404, detail="Parking location not found")
    return facility


def _zone(db: DbSession, facility: Facility, vehicle_type: VehicleType | None = None) -> ParkingZone:
    zone = db.scalar(
        select(ParkingZone).where(
            ParkingZone.facility_id == facility.id,
            ParkingZone.vehicle_type == vehicle_type if vehicle_type else True,
            ParkingZone.is_active.is_(True),
        ).order_by(ParkingZone.id)
    )
    if not zone:
        raise HTTPException(status_code=409, detail="A compatible parking zone is not configured")
    return zone


def _facility_read(db: DbSession, facility: Facility) -> CollegeFacilityRead:
    slots = list(db.scalars(select(ParkingSlot).join(ParkingZone).where(ParkingZone.facility_id == facility.id, ParkingZone.is_active.is_(True), ParkingSlot.is_active.is_(True)).order_by(ParkingZone.name, ParkingSlot.id)))
    parked_vehicles = dict(db.execute(
        select(ParkingSession.slot_id, Vehicle.registration_number)
        .join(Vehicle, Vehicle.id == ParkingSession.vehicle_id)
        .where(ParkingSession.facility_id == facility.id, ParkingSession.status == ParkingSessionStatus.ACTIVE)
    ).all())
    occupied = sum(slot.status == SlotStatus.OCCUPIED for slot in slots)
    return CollegeFacilityRead(
        id=facility.id, name=facility.name, address=facility.address,
        latitude=facility.latitude, longitude=facility.longitude, timezone=facility.timezone,
        capacity=len(slots), occupied=occupied, available=sum(slot.status == SlotStatus.AVAILABLE for slot in slots),
        last_updated=datetime.now(UTC),
        slots=[CollegeSlotRead(slot_id=s.id, code=s.slot_code, status=s.status.value, vehicle_number=parked_vehicles.get(s.id) if s.status == SlotStatus.OCCUPIED else None) for s in slots],
    )


def _session_read(session: ParkingSession, include_private: bool = True) -> CollegeSessionRead:
    duration = None
    if session.entry_time:
        end = session.exit_time or datetime.now(UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        entry = session.entry_time if session.entry_time.tzinfo else session.entry_time.replace(tzinfo=UTC)
        duration = max(0, int((end - entry).total_seconds() // 60))
    return CollegeSessionRead(
        id=session.id, ticket_id=session.ticket_id, facility_id=session.facility_id, place_name=session.facility.name, student_name=session.user.full_name,
        phone=session.user.phone if include_private else None,
        vehicle_number=session.vehicle.registration_number, space=session.slot.slot_code,
        entry_source=session.entry_source, exit_source=session.exit_source,
        entry_time=session.entry_time, exit_time=session.exit_time, duration_minutes=duration,
        status=session.status,
    )


@router.get("/facility", response_model=CollegeFacilityRead)
def facility(db: DbSession, user: CurrentUser, facility_id: int | None = None) -> CollegeFacilityRead:
    return _facility_read(db, _facility(db, facility_id))


@router.get("/locations", response_model=list[CollegeFacilityRead])
def locations(db: DbSession, user: CurrentUser) -> list[CollegeFacilityRead]:
    return [_facility_read(db, f) for f in db.scalars(select(Facility).where(Facility.is_active.is_(True)).order_by(Facility.name))]


@router.post("/admin/locations", response_model=CollegeFacilityRead, status_code=201)
def add_location(data: CollegeConfigUpdate, db: DbSession, admin: User = AdminUser) -> CollegeFacilityRead:
    facility = Facility(name=data.name.strip(), address=data.address.strip(), latitude=data.latitude, longitude=data.longitude, total_capacity=data.capacity, timezone=data.timezone, is_active=True)
    db.add(facility)
    try:
        db.flush()
        zone = ParkingZone(facility_id=facility.id, name="Main parking", vehicle_type=VehicleType.MOTORCYCLE, capacity=data.capacity, is_active=True)
        db.add(zone)
        db.flush()
        for index in range(data.capacity):
            db.add(ParkingSlot(zone_id=zone.id, row_label="P", slot_code=f"P-{index+1:03d}", status=SlotStatus.AVAILABLE, is_active=True))
        record_audit(db, actor_user_id=admin.id, action="CREATE", entity_type="parking_location", entity_id=facility.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A location with this name already exists") from exc
    return _facility_read(db, facility)


@router.get("/profile", response_model=CollegeProfileRead)
def profile(db: DbSession, user: CurrentUser) -> CollegeProfileRead:
    vehicle = db.scalar(select(Vehicle).where(Vehicle.user_id == user.id).order_by(Vehicle.id))
    return CollegeProfileRead(
        full_name=user.full_name, email=user.email, phone=user.phone,
        registration_number=vehicle.registration_number if vehicle else None,
        vehicle_type=vehicle.vehicle_type if vehicle else None,
    )


@router.put("/profile", response_model=CollegeProfileRead)
def update_profile(data: CollegeProfileUpdate, db: DbSession, user: CurrentUser) -> CollegeProfileRead:
    active = db.scalar(select(ParkingSession.id).where(ParkingSession.user_id == user.id, ParkingSession.status == ParkingSessionStatus.ACTIVE))
    existing = db.scalar(select(Vehicle).where(Vehicle.user_id == user.id).order_by(Vehicle.id))
    if active and existing and existing.registration_number != data.registration_number.upper():
        raise HTTPException(status_code=409, detail="Vehicle details cannot change during an active parking session")
    user.full_name, user.phone = data.full_name.strip(), data.phone
    if existing:
        if existing.registration_number != data.registration_number.upper():
            conflict = db.scalar(select(Vehicle.id).where(Vehicle.registration_number == data.registration_number.upper(), Vehicle.id != existing.id))
            if conflict:
                raise HTTPException(status_code=409, detail="Vehicle registration is already registered")
            existing.registration_number = data.registration_number.upper()
    else:
        existing = Vehicle(user_id=user.id, registration_number=data.registration_number.upper(), vehicle_type=VehicleType.MOTORCYCLE)
        db.add(existing)
    db.commit()
    return profile(db, user)


@router.post("/entry", response_model=CollegeActionResponse, status_code=201)
def entry(db: DbSession, user: CurrentUser, facility_id: int | None = None) -> CollegeActionResponse:
    facility = _facility(db, facility_id)
    vehicle = db.scalar(select(Vehicle).where(Vehicle.user_id == user.id).order_by(Vehicle.id))
    if not vehicle or vehicle.vehicle_type != VehicleType.MOTORCYCLE:
        raise HTTPException(status_code=400, detail="Complete a two-wheeler profile before parking")
    zone = _zone(db, facility, vehicle.vehicle_type)
    session = create_entry(db, ParkingEntryRequest(vehicle_id=vehicle.id, facility_id=facility.id, zone_id=zone.id, entry_method=EntryMethod.SELF_SERVICE), user)
    session.entry_source = "STUDENT_BUTTON"
    record_audit(db, actor_user_id=user.id, action="COLLEGE_ENTRY", entity_type="parking_session", entity_id=session.id, details={"source": "STUDENT_BUTTON"})
    db.commit()
    session = get_session_by_ticket(db, session.ticket_id)
    return CollegeActionResponse(session=_session_read(session), facility=_facility_read(db, facility))


@router.post("/exit", response_model=CollegeActionResponse)
def exit_parking(db: DbSession, user: CurrentUser, facility_id: int | None = None) -> CollegeActionResponse:
    facility = _facility(db, facility_id)
    session = db.scalar(select(ParkingSession).options(joinedload(ParkingSession.user), joinedload(ParkingSession.vehicle), joinedload(ParkingSession.slot), joinedload(ParkingSession.zone), joinedload(ParkingSession.facility)).where(ParkingSession.facility_id == facility.id, ParkingSession.user_id == user.id, ParkingSession.status == ParkingSessionStatus.ACTIVE).with_for_update())
    if not session:
        raise HTTPException(status_code=404, detail="No active parking session")
    close_session(db, ticket_id=session.ticket_id, requester=user, method=EntryMethod.MANUAL)
    session.exit_source = "STUDENT_BUTTON"
    record_audit(db, actor_user_id=user.id, action="COLLEGE_EXIT", entity_type="parking_session", entity_id=session.id, details={"source": "STUDENT_BUTTON"})
    db.commit()
    session = db.scalar(select(ParkingSession).options(joinedload(ParkingSession.user), joinedload(ParkingSession.vehicle), joinedload(ParkingSession.slot), joinedload(ParkingSession.zone), joinedload(ParkingSession.facility)).where(ParkingSession.id == session.id))
    return CollegeActionResponse(session=_session_read(session), facility=_facility_read(db, facility))


@router.get("/my-sessions", response_model=list[CollegeSessionRead])
def my_sessions(db: DbSession, user: CurrentUser, facility_id: int | None = None) -> list[CollegeSessionRead]:
    sessions = db.scalars(select(ParkingSession).options(joinedload(ParkingSession.user), joinedload(ParkingSession.vehicle), joinedload(ParkingSession.slot)).where(ParkingSession.user_id == user.id, ParkingSession.facility_id == facility_id if facility_id else True).order_by(ParkingSession.entry_time.desc()).limit(50))
    return [_session_read(item, include_private=False) for item in sessions]


@router.get("/admin/sessions", response_model=list[CollegeSessionRead])
def admin_sessions(db: DbSession, admin: User = AdminUser, facility_id: int | None = None) -> list[CollegeSessionRead]:
    sessions = db.scalars(select(ParkingSession).options(joinedload(ParkingSession.user), joinedload(ParkingSession.vehicle), joinedload(ParkingSession.slot)).where(ParkingSession.facility_id == facility_id if facility_id else True).order_by(ParkingSession.entry_time.desc()).limit(500))
    return [_session_read(item) for item in sessions]


@router.post("/admin/manual-entry", response_model=CollegeActionResponse, status_code=201)
def manual_entry(data: AdminManualEntry, db: DbSession, admin: User = AdminUser) -> CollegeActionResponse:
    facility = _facility(db)
    vehicle = db.scalar(select(Vehicle).where(Vehicle.user_id == data.user_id, Vehicle.vehicle_type == VehicleType.MOTORCYCLE).order_by(Vehicle.id))
    if not vehicle:
        raise HTTPException(status_code=404, detail="Student has no registered two-wheeler")
    zone = _zone(db, facility)
    session = create_entry(db, ParkingEntryRequest(vehicle_id=vehicle.id, facility_id=facility.id, zone_id=zone.id, user_id=data.user_id, entry_method=EntryMethod.MANUAL), admin)
    session.entry_source = "ADMIN_MANUAL"
    record_audit(db, actor_user_id=admin.id, action="COLLEGE_MANUAL_ENTRY", entity_type="parking_session", entity_id=session.id, details={"reason": data.reason, "source": "ADMIN_MANUAL"})
    db.commit()
    return CollegeActionResponse(session=_session_read(get_session_by_ticket(db, session.ticket_id)), facility=_facility_read(db, facility))


@router.post("/admin/manual-exit", response_model=CollegeActionResponse)
def manual_exit(data: AdminManualExit, db: DbSession, admin: User = AdminUser) -> CollegeActionResponse:
    facility = _facility(db)
    session = get_session_by_ticket(db, data.ticket_id)
    if session.facility_id != facility.id:
        raise HTTPException(status_code=404, detail="Parking session not found")
    close_session(db, ticket_id=session.ticket_id, requester=admin, method=EntryMethod.MANUAL)
    session.exit_source = "ADMIN_MANUAL"
    record_audit(db, actor_user_id=admin.id, action="COLLEGE_MANUAL_EXIT", entity_type="parking_session", entity_id=session.id, details={"reason": data.reason, "source": "ADMIN_MANUAL"})
    db.commit()
    return CollegeActionResponse(session=_session_read(get_session_by_ticket(db, session.ticket_id)), facility=_facility_read(db, facility))


@router.put("/admin/config", response_model=CollegeFacilityRead)
def update_config(data: CollegeConfigUpdate, db: DbSession, admin: User = AdminUser, facility_id: int | None = None) -> CollegeFacilityRead:
    facility = _facility(db, facility_id)
    zones = list(db.scalars(select(ParkingZone).where(ParkingZone.facility_id == facility.id, ParkingZone.is_active.is_(True))))
    if len(zones) != 1:
        raise HTTPException(status_code=409, detail="Manage capacities for multi-zone locations in zone management")
    zone = zones[0]
    slots = list(db.scalars(select(ParkingSlot).where(ParkingSlot.zone_id == zone.id).order_by(ParkingSlot.id)))
    target_slots = slots[:data.capacity]
    removed = slots[data.capacity:]
    if any(slot.status == SlotStatus.OCCUPIED for slot in removed):
        raise HTTPException(status_code=409, detail="Cannot remove occupied slots. Free them first.")
    for slot in target_slots:
        slot.is_active = True
    for slot in removed:
        slot.is_active = False
    for index in range(len(slots), data.capacity):
        db.add(ParkingSlot(zone_id=zone.id, row_label="P", slot_code=f"P-{index+1:03d}", status=SlotStatus.AVAILABLE, is_active=True))
    facility.name, facility.address = data.name.strip(), data.address.strip()
    facility.latitude, facility.longitude = data.latitude, data.longitude
    facility.total_capacity, facility.timezone = data.capacity, data.timezone
    facility.permitted_email_domains = ",".join(domain.strip().lower() for domain in data.permitted_email_domains if domain.strip()) or None
    zone.capacity = data.capacity
    record_audit(db, actor_user_id=admin.id, action="UPDATE", entity_type="parking_location", entity_id=facility.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A location with this name already exists") from exc
    return _facility_read(db, facility)


@router.get("/qr", response_model=CollegeQrRead)
def qr_links(db: DbSession, admin: User = AdminUser, facility_id: int | None = None) -> CollegeQrRead:
    facility = _facility(db, facility_id)
    query = urlencode({"facility_id": facility.id, "latitude": facility.latitude if facility.latitude is not None else "", "longitude": facility.longitude if facility.longitude is not None else ""})
    base = get_settings().frontend_base_url.rstrip("/")
    return CollegeQrRead(entry_path=f"{base}/user?flow=entry&{query}", exit_path=f"{base}/user?flow=exit&{query}")


@router.get("/qr/{direction}.png")
def qr_image(direction: str, db: DbSession, admin: User = AdminUser, facility_id: int | None = None) -> Response:
    links = qr_links(db, admin, facility_id)
    path = links.entry_path if direction == "entry" else links.exit_path if direction == "exit" else None
    if not path:
        raise HTTPException(status_code=404, detail="QR direction not found")
    return Response(qr_png_bytes(path), media_type="image/png", headers={"Content-Disposition": f"attachment; filename=location-{facility_id or 'default'}-{direction}.png"})
