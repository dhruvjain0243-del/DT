from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models.enums import SlotStatus, VehicleType


class FacilityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    address: str = Field(min_length=5, max_length=1000)
    total_capacity: int = Field(gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    distance_km: float = Field(default=0, ge=0)
    price_per_hour: float = Field(default=0, ge=0)
    is_active: bool = True


class FacilityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    address: str | None = Field(default=None, min_length=5, max_length=1000)
    total_capacity: int | None = Field(default=None, gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    distance_km: float | None = Field(default=None, ge=0)
    price_per_hour: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class FacilityRead(FacilityCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    vehicle_type: VehicleType
    capacity: int = Field(gt=0)
    is_active: bool = True


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    vehicle_type: VehicleType | None = None
    capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ZoneRead(ZoneCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    facility_id: int


class SlotCreate(BaseModel):
    slot_code: str = Field(min_length=1, max_length=60)
    row_label: str | None = Field(default=None, max_length=30)
    status: SlotStatus = SlotStatus.AVAILABLE
    is_active: bool = True


class SlotBulkCreate(BaseModel):
    slots: list[SlotCreate] = Field(min_length=1, max_length=500)


class SlotUpdate(BaseModel):
    slot_code: str | None = Field(default=None, min_length=1, max_length=60)
    row_label: str | None = Field(default=None, max_length=30)
    status: SlotStatus | None = None
    is_active: bool | None = None


class SlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    row_label: str | None
    slot_code: str
    status: SlotStatus
    qr_code_value: str | None
    is_active: bool


class SlotQRResponse(BaseModel):
    slot_id: int
    qr_token: str
    png_base64: str


class SlotCorrectionRequest(BaseModel):
    slot_id: int = Field(gt=0)


class CapacityValidation(BaseModel):
    facility_capacity: int
    zone_capacities: list[int]

    @model_validator(mode="after")
    def zones_fit_facility(self) -> "CapacityValidation":
        if sum(self.zone_capacities) > self.facility_capacity:
            raise ValueError("Zone capacities exceed facility capacity")
        return self
