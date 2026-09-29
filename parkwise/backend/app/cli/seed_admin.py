from __future__ import annotations

import argparse
import os
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from ..core.database import get_session_factory
from ..core.security import hash_password
from ..models import Facility, ParkingSlot, ParkingZone, SlotStatus, User, UserRole, VehicleType


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the first PARKWISE administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="PARKWISE Administrator")
    parser.add_argument("--password", default=os.getenv("SEED_ADMIN_PASSWORD"))
    parser.add_argument("--with-demo-data", action="store_true")
    return parser.parse_args()


def seed_demo_data(db) -> None:
    if db.scalar(select(Facility.id).where(Facility.name == "Campus Main Parking")):
        return
    facility = Facility(
        name="Campus Main Parking",
        address="Main campus entrance",
        total_capacity=12,
        distance_km=0.3,
        price_per_hour=10,
        is_active=True,
    )
    db.add(facility)
    db.flush()
    zone = ParkingZone(
        facility_id=facility.id,
        name="Ground floor",
        vehicle_type=VehicleType.CAR,
        capacity=12,
        is_active=True,
    )
    db.add(zone)
    db.flush()
    for number in range(1, 13):
        db.add(
            ParkingSlot(
                zone_id=zone.id,
                row_label="A" if number <= 6 else "B",
                slot_code=f"S{number:02d}",
                status=SlotStatus.AVAILABLE,
                is_active=True,
            )
        )


def main() -> None:
    args = parse_args()
    password = args.password or getpass("Admin password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    factory = get_session_factory()
    with factory() as db:
        try:
            email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
        except ValidationError as exc:
            raise SystemExit("A valid administrator email address is required") from exc
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit(f"A user already exists for {email}")
        admin = User(
            full_name=args.full_name.strip(),
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        if args.with_demo_data:
            seed_demo_data(db)
        db.commit()
        print(f"Created ADMIN user: {email}")
        if args.with_demo_data:
            print("Created demo facility, zone, and 12 parking slots")


if __name__ == "__main__":
    main()
