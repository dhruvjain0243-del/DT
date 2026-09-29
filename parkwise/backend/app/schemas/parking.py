from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import EntryMethod, ParkingSessionStatus, VehicleType


class ParkingEntryRequest(BaseModel):
    vehicle_id: int = Field(gt=0)
    facility_id: int = Field(gt=0)
    zone_id: int | None = Field(default=None, gt=0)
    slot_id: int | None = Field(default=None, gt=0)
    user_id: int | None = Field(default=None, gt=0)
    entry_method: EntryMethod = EntryMethod.SELF_SERVICE
    slot_qr_token: str | None = Field(default=None, min_length=20)


class ParkingExitRequest(BaseModel):
    ticket_id: str = Field(min_length=8, max_length=64)
    qr_token: str = Field(min_length=20)


class ParkingManualExitRequest(BaseModel):
    ticket_id: str = Field(min_length=8, max_length=64)


class ParkingSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: str
    user_id: int
    vehicle_id: int
    facility_id: int
    zone_id: int
    slot_id: int
    entry_time: datetime
    exit_time: datetime | None
    status: ParkingSessionStatus
    entry_method: EntryMethod
    exit_method: EntryMethod | None
    created_at: datetime


class TicketResponse(ParkingSessionRead):
    facility_name: str
    zone_name: str
    row_label: str | None
    slot_code: str
    registration_number: str
    qr_token: str
    qr_png_base64: str


class ExitResponse(BaseModel):
    ticket_id: str
    status: ParkingSessionStatus
    registration_number: str
    vehicle_type: VehicleType
    slot_id: int
    slot_code: str
    entry_time: datetime
    exit_time: datetime
    duration_minutes: int
    message: str


class FindVehicleResponse(BaseModel):
    ticket_id: str
    status: ParkingSessionStatus
    facility_id: int
    facility_name: str
    facility_address: str
    latitude: float | None
    longitude: float | None
    zone_id: int
    zone_name: str
    row_label: str | None
    slot_id: int
    slot_code: str
    entry_time: datetime


class ConfirmSlotRequest(BaseModel):
    ticket_id: str = Field(min_length=8, max_length=64)
    slot_qr_token: str = Field(min_length=20)


class AvailabilityZone(BaseModel):
    zone_id: int
    zone_name: str
    vehicle_type: VehicleType
    total_capacity: int
    occupied_spaces: int
    available_spaces: int
    occupancy_percentage: float


class AvailabilityFacility(BaseModel):
    facility_id: int
    facility_name: str
    total_capacity: int
    occupied_spaces: int
    available_spaces: int
    occupancy_percentage: float
    last_update_time: datetime
    by_vehicle_type: dict[str, dict[str, int]]
    zones: list[AvailabilityZone] = []
