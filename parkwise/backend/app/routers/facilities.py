from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from ..dependencies import CurrentUser, DbSession, require_roles
from ..models import Facility, ParkingSession, ParkingSessionStatus, ParkingSlot, ParkingZone, User, UserRole
from ..schemas.common import MessageResponse
from ..schemas.resources import FacilityCreate, FacilityRead, FacilityUpdate, ZoneCreate, ZoneRead, ZoneUpdate
from ..services.audit import record_audit


router = APIRouter(prefix="/api", tags=["facilities"])
AdminUser = Depends(require_roles(UserRole.ADMIN))


@router.post("/facilities", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
def create_facility(data: FacilityCreate, db: DbSession, admin: User = AdminUser) -> Facility:
    if db.scalar(select(Facility.id).where(Facility.name == data.name)):
        raise HTTPException(status_code=409, detail="Facility name already exists")
    facility = Facility(**data.model_dump())
    db.add(facility)
    db.flush()
    record_audit(db, actor_user_id=admin.id, action="CREATE", entity_type="facility", entity_id=facility.id)
    db.commit()
    db.refresh(facility)
    return facility


@router.get("/facilities", response_model=list[FacilityRead])
def list_facilities(user: CurrentUser, db: DbSession) -> list[Facility]:
    return list(db.scalars(select(Facility).order_by(Facility.name)))


def _facility_or_404(db: DbSession, facility_id: int) -> Facility:
    facility = db.get(Facility, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility


@router.get("/facilities/{facility_id}", response_model=FacilityRead)
def get_facility(facility_id: int, user: CurrentUser, db: DbSession) -> Facility:
    return _facility_or_404(db, facility_id)


@router.put("/facilities/{facility_id}", response_model=FacilityRead)
def update_facility(
    facility_id: int, data: FacilityUpdate, db: DbSession, admin: User = AdminUser
) -> Facility:
    facility = _facility_or_404(db, facility_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(facility, key, value)
    zone_capacity = int(
        db.scalar(select(func.coalesce(func.sum(ParkingZone.capacity), 0)).where(ParkingZone.facility_id == facility.id)) or 0
    )
    if facility.total_capacity < zone_capacity:
        raise HTTPException(status_code=400, detail="Facility capacity cannot be below configured zone capacity")
    record_audit(db, actor_user_id=admin.id, action="UPDATE", entity_type="facility", entity_id=facility.id)
    db.commit()
    db.refresh(facility)
    return facility


@router.delete("/facilities/{facility_id}", response_model=MessageResponse)
def delete_facility(facility_id: int, db: DbSession, admin: User = AdminUser) -> MessageResponse:
    facility = _facility_or_404(db, facility_id)
    active = db.scalar(
        select(ParkingSession.id).where(
            ParkingSession.facility_id == facility.id,
            ParkingSession.status == ParkingSessionStatus.ACTIVE,
        ).limit(1)
    )
    if active:
        raise HTTPException(status_code=409, detail="Facility has active parking sessions")
    facility.is_active = False
    for zone in facility.zones:
        zone.is_active = False
    record_audit(db, actor_user_id=admin.id, action="DEACTIVATE", entity_type="facility", entity_id=facility.id)
    db.commit()
    return MessageResponse(message="Facility deactivated")


@router.post("/facilities/{facility_id}/zones", response_model=ZoneRead, status_code=201)
def create_zone(
    facility_id: int, data: ZoneCreate, db: DbSession, admin: User = AdminUser
) -> ParkingZone:
    facility = _facility_or_404(db, facility_id)
    configured = int(
        db.scalar(select(func.coalesce(func.sum(ParkingZone.capacity), 0)).where(ParkingZone.facility_id == facility_id)) or 0
    )
    if configured + data.capacity > facility.total_capacity:
        raise HTTPException(status_code=400, detail="Zone capacities would exceed facility capacity")
    zone = ParkingZone(facility_id=facility_id, **data.model_dump())
    db.add(zone)
    db.flush()
    record_audit(db, actor_user_id=admin.id, action="CREATE", entity_type="zone", entity_id=zone.id)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/facilities/{facility_id}/zones", response_model=list[ZoneRead])
def list_zones(facility_id: int, user: CurrentUser, db: DbSession) -> list[ParkingZone]:
    _facility_or_404(db, facility_id)
    return list(db.scalars(select(ParkingZone).where(ParkingZone.facility_id == facility_id).order_by(ParkingZone.name)))


def _zone_or_404(db: DbSession, zone_id: int) -> ParkingZone:
    zone = db.get(ParkingZone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Parking zone not found")
    return zone


@router.put("/zones/{zone_id}", response_model=ZoneRead)
def update_zone(zone_id: int, data: ZoneUpdate, db: DbSession, admin: User = AdminUser) -> ParkingZone:
    zone = _zone_or_404(db, zone_id)
    values = data.model_dump(exclude_unset=True)
    new_capacity = values.get("capacity", zone.capacity)
    slot_count = int(
        db.scalar(select(func.count(ParkingSlot.id)).where(ParkingSlot.zone_id == zone.id)) or 0
    )
    if new_capacity < slot_count:
        raise HTTPException(status_code=400, detail="Zone capacity cannot be below its configured slot count")
    others = int(
        db.scalar(
            select(func.coalesce(func.sum(ParkingZone.capacity), 0)).where(
                ParkingZone.facility_id == zone.facility_id, ParkingZone.id != zone.id
            )
        )
        or 0
    )
    if others + new_capacity > zone.facility.total_capacity:
        raise HTTPException(status_code=400, detail="Zone capacities would exceed facility capacity")
    for key, value in values.items():
        setattr(zone, key, value)
    record_audit(db, actor_user_id=admin.id, action="UPDATE", entity_type="zone", entity_id=zone.id)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}", response_model=MessageResponse)
def delete_zone(zone_id: int, db: DbSession, admin: User = AdminUser) -> MessageResponse:
    zone = _zone_or_404(db, zone_id)
    active = db.scalar(
        select(ParkingSession.id).where(
            ParkingSession.zone_id == zone.id,
            ParkingSession.status == ParkingSessionStatus.ACTIVE,
        ).limit(1)
    )
    if active:
        raise HTTPException(status_code=409, detail="Zone has active parking sessions")
    zone.is_active = False
    for slot in zone.slots:
        slot.is_active = False
    record_audit(db, actor_user_id=admin.id, action="DEACTIVATE", entity_type="zone", entity_id=zone.id)
    db.commit()
    return MessageResponse(message="Zone deactivated")
