from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Facility, ParkingSession, ParkingSessionStatus, ParkingZone, Vehicle
from ..schemas.parking import AvailabilityFacility, AvailabilityZone


def _active_count_for_facility(db: Session, facility_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ParkingSession.id)).where(
                ParkingSession.facility_id == facility_id,
                ParkingSession.status == ParkingSessionStatus.ACTIVE,
            )
        )
        or 0
    )


def facility_availability(
    db: Session, facility: Facility, include_zones: bool = True
) -> AvailabilityFacility:
    occupied = _active_count_for_facility(db, facility.id)
    available = max(0, facility.total_capacity - occupied)
    zones: list[AvailabilityZone] = []
    type_totals: dict[str, dict[str, int]] = {}

    zone_rows = db.scalars(
        select(ParkingZone).where(
            ParkingZone.facility_id == facility.id,
            ParkingZone.is_active.is_(True),
        ).order_by(ParkingZone.name)
    ).all()
    for zone in zone_rows:
        zone_occupied = int(
            db.scalar(
                select(func.count(ParkingSession.id)).where(
                    ParkingSession.zone_id == zone.id,
                    ParkingSession.status == ParkingSessionStatus.ACTIVE,
                )
            )
            or 0
        )
        zone_available = max(0, zone.capacity - zone_occupied)
        kind = zone.vehicle_type.value
        aggregate = type_totals.setdefault(
            kind, {"total_capacity": 0, "occupied_spaces": 0, "available_spaces": 0}
        )
        aggregate["total_capacity"] += zone.capacity
        aggregate["occupied_spaces"] += zone_occupied
        aggregate["available_spaces"] += zone_available
        if include_zones:
            zones.append(
                AvailabilityZone(
                    zone_id=zone.id,
                    zone_name=zone.name,
                    vehicle_type=zone.vehicle_type,
                    total_capacity=zone.capacity,
                    occupied_spaces=zone_occupied,
                    available_spaces=zone_available,
                    occupancy_percentage=round(
                        (zone_occupied / zone.capacity * 100) if zone.capacity else 0, 2
                    ),
                )
            )
    return AvailabilityFacility(
        facility_id=facility.id,
        facility_name=facility.name,
        total_capacity=facility.total_capacity,
        occupied_spaces=occupied,
        available_spaces=available,
        occupancy_percentage=round(
            (occupied / facility.total_capacity * 100) if facility.total_capacity else 0, 2
        ),
        last_update_time=datetime.now(UTC),
        by_vehicle_type=type_totals,
        zones=zones,
    )


def all_availability(db: Session) -> list[AvailabilityFacility]:
    facilities = db.scalars(
        select(Facility).where(Facility.is_active.is_(True)).order_by(Facility.name)
    ).all()
    return [facility_availability(db, facility) for facility in facilities]
