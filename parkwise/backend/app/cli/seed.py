"""Idempotently create local development demo records and credentials."""

from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select

from ..core.database import get_session_factory
from ..core.security import create_qr_token, hash_password
from ..models import (
    EntryMethod,
    Facility,
    Feedback,
    FeedbackCategory,
    FeedbackStatus,
    ParkingSession,
    ParkingSessionStatus,
    ParkingSlot,
    ParkingZone,
    Prediction,
    SlotStatus,
    User,
    UserRole,
    Vehicle,
    VehicleType,
)
from ..models.entities import utcnow


DEMO_USERS = (
    ("admin@parkwise.org", "PARKWISE Demo Administrator", UserRole.ADMIN),
    ("attendant@parkwise.org", "PARKWISE Demo Attendant", UserRole.ATTENDANT),
    ("student@parkwise.org", "PARKWISE Demo Student", UserRole.STUDENT),
    ("staff@parkwise.org", "PARKWISE Demo Staff", UserRole.STAFF),
    ("visitor@parkwise.org", "PARKWISE Demo Visitor", UserRole.VISITOR),
)


def new_development_password() -> str:
    """Return a high-entropy, one-time printed development credential."""
    return f"{secrets.token_urlsafe(18)}aA1!"


def get_or_create_user(db, email: str, name: str, role: UserRole) -> tuple[User, str | None]:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        changed = False
        if user.role != role:
            user.role = role
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            db.flush()
        return user, None
    password = new_development_password()
    user = User(
        full_name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user, password


def get_or_create_vehicle(db, user: User, registration: str, kind: VehicleType) -> Vehicle:
    vehicle = db.scalar(select(Vehicle).where(Vehicle.registration_number == registration))
    if vehicle:
        if vehicle.user_id != user.id or vehicle.vehicle_type != kind:
            vehicle.user_id = user.id
            vehicle.vehicle_type = kind
            db.flush()
        return vehicle
    vehicle = Vehicle(user_id=user.id, registration_number=registration, vehicle_type=kind)
    db.add(vehicle)
    db.flush()
    return vehicle


def get_or_create_slot(db, zone: ParkingZone, code: str, row: str) -> ParkingSlot:
    slot = db.scalar(
        select(ParkingSlot).where(
            ParkingSlot.zone_id == zone.id,
            ParkingSlot.slot_code == code,
        )
    )
    if slot:
        if not slot.qr_code_value:
            slot.qr_code_value = create_qr_token(str(slot.id), "slot_qr")
        return slot
    slot = ParkingSlot(
        zone_id=zone.id,
        slot_code=code,
        row_label=row,
        status=SlotStatus.AVAILABLE,
        is_active=True,
    )
    db.add(slot)
    db.flush()
    slot.qr_code_value = create_qr_token(str(slot.id), "slot_qr")
    db.flush()
    return slot


def seed(db) -> tuple[dict[str, User], dict[str, str], Facility]:
    users: dict[str, User] = {}
    new_passwords: dict[str, str] = {}
    for email, name, role in DEMO_USERS:
        user, password = get_or_create_user(db, email, name, role)
        users[email] = user
        if password:
            new_passwords[email] = password

    facility = db.scalar(
        select(Facility).where(Facility.name == "PARKWISE College Demo")
    )
    if not facility:
        facility = Facility(
            name="PARKWISE College Demo",
            address="100 College Avenue, Main Campus",
            total_capacity=100,
            latitude=12.9716,
            longitude=77.5946,
            distance_km=0.3,
            price_per_hour=10,
            is_active=True,
        )
        db.add(facility)
        db.flush()
    else:
        facility.total_capacity = 100
        facility.is_active = True

    zones: dict[str, ParkingZone] = {}
    for name, capacity, vehicle_type in (
        ("Two-wheeler zone A", 50, VehicleType.MOTORCYCLE),
        ("Two-wheeler zone B", 50, VehicleType.MOTORCYCLE),
    ):
        zone = db.scalar(
            select(ParkingZone).where(
                ParkingZone.facility_id == facility.id,
                ParkingZone.name == name,
            )
        )
        if not zone:
            zone = ParkingZone(
                facility_id=facility.id,
                name=name,
                vehicle_type=vehicle_type,
                capacity=capacity,
                is_active=True,
            )
            db.add(zone)
            db.flush()
        else:
            zone.capacity = capacity
            zone.vehicle_type = vehicle_type
            zone.is_active = True
        zones[name] = zone

    slots: list[ParkingSlot] = []
    for zone_name, prefix in (("Two-wheeler zone A", "A"), ("Two-wheeler zone B", "B")):
        for index in range(1, 51):
            slots.append(get_or_create_slot(db, zones[zone_name], f"{prefix}-{index:03d}", prefix))

    demo_vehicles = (
        ("student@parkwise.org", "DEMO-STU-001", VehicleType.MOTORCYCLE),
        ("staff@parkwise.org", "DEMO-STF-001", VehicleType.MOTORCYCLE),
        ("visitor@parkwise.org", "DEMO-VIS-001", VehicleType.MOTORCYCLE),
    )
    vehicles: list[Vehicle] = []
    for email, registration, kind in demo_vehicles:
        vehicles.append(get_or_create_vehicle(db, users[email], registration, kind))

    history_specs = (
        (vehicles[0], "DEMO-HIST-STUDENT-001", 1),
        (vehicles[1], "DEMO-HIST-STAFF-001", 2),
        (vehicles[2], "DEMO-HIST-VISITOR-001", 3),
    )
    for vehicle, ticket_id, slot_number in history_specs:
        existing = db.scalar(
            select(ParkingSession.id).where(ParkingSession.ticket_id == ticket_id)
        )
        if existing:
            continue
        zone = zones["Two-wheeler zone A"]
        slot = next(item for item in slots if item.zone_id == zone.id and item.slot_code == f"A-{slot_number:03d}")
        exit_time = utcnow()
        entry_time = exit_time - timedelta(days=slot_number, hours=2)
        db.add(
            ParkingSession(
                ticket_id=ticket_id,
                user_id=vehicle.user_id,
                vehicle_id=vehicle.id,
                facility_id=facility.id,
                zone_id=zone.id,
                slot_id=slot.id,
                entry_time=entry_time,
                exit_time=exit_time,
                status=ParkingSessionStatus.COMPLETED,
                entry_method=EntryMethod.QR,
                exit_method=EntryMethod.QR,
            )
        )

    if not db.scalar(select(Prediction.id).where(Prediction.facility_id == facility.id)):
        now = utcnow()
        db.add(
            Prediction(
                facility_id=facility.id,
                zone_id=zones["Two-wheeler zone A"].id,
                prediction_time=now,
                target_time=now + timedelta(minutes=30),
                predicted_available_spaces=92,
                model_version="demo-seed-simulated-v1",
            )
        )

    if not db.scalar(select(Feedback.id).where(Feedback.user_id == users["student@parkwise.org"].id)):
        db.add(
            Feedback(
                user_id=users["student@parkwise.org"].id,
                category=FeedbackCategory.AVAILABILITY,
                description="Demo feedback: zone signage was easy to follow.",
                reported_available_spaces=92,
                status=FeedbackStatus.OPEN,
            )
        )
    db.flush()
    return users, new_passwords, facility


def main() -> None:
    factory = get_session_factory()
    with factory() as db:
        users, passwords, facility = seed(db)
        db.commit()
        print("PARKWISE DEVELOPMENT DEMO CREDENTIALS (local development only)")
        print("These randomly generated credentials are printed only when an account is first created.")
        for email, _, role in DEMO_USERS:
            if email in passwords:
                print(f"{role.value}: {email} / {passwords[email]}")
            else:
                print(f"{role.value}: {email} / existing account kept; password not reset")
        print(f"Facility: {facility.name} (capacity {facility.total_capacity})")
        print("Zones: Two-wheeler zone A (50), Two-wheeler zone B (50)")
        print("Slots: 100 available two-wheeler slots")
        print("Seed is idempotent; rerunning does not duplicate demo records.")


if __name__ == "__main__":
    main()
