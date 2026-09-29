from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..dependencies import CurrentUser, DbSession
from ..models import Vehicle
from ..schemas.auth import VehicleCreate, VehicleRead


router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(data: VehicleCreate, user: CurrentUser, db: DbSession) -> Vehicle:
    if db.scalar(
        select(Vehicle.id).where(Vehicle.registration_number == data.registration_number)
    ):
        raise HTTPException(status_code=409, detail="Vehicle registration already exists")
    vehicle = Vehicle(user_id=user.id, **data.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/mine", response_model=list[VehicleRead])
def my_vehicles(user: CurrentUser, db: DbSession) -> list[Vehicle]:
    return list(
        db.scalars(select(Vehicle).where(Vehicle.user_id == user.id).order_by(Vehicle.created_at))
    )
