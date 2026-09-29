from fastapi import APIRouter, HTTPException

from ..dependencies import CurrentUser, DbSession
from ..models import Facility
from ..schemas.parking import AvailabilityFacility, AvailabilityZone
from ..services.availability import all_availability, facility_availability


router = APIRouter(prefix="/api/availability", tags=["availability"])


@router.get("", response_model=list[AvailabilityFacility])
def availability(user: CurrentUser, db: DbSession) -> list[AvailabilityFacility]:
    return all_availability(db)


@router.get("/{facility_id}", response_model=AvailabilityFacility)
def availability_for_facility(
    facility_id: int, user: CurrentUser, db: DbSession
) -> AvailabilityFacility:
    facility = db.get(Facility, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility_availability(db, facility)


@router.get("/{facility_id}/zones", response_model=list[AvailabilityZone])
def availability_by_zone(
    facility_id: int, user: CurrentUser, db: DbSession
) -> list[AvailabilityZone]:
    facility = db.get(Facility, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility_availability(db, facility).zones
