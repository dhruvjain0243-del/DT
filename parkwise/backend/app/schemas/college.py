from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import ParkingSessionStatus, VehicleType


class CollegeConfigUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    address: str = Field(min_length=5, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(gt=0, le=5000)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    permitted_email_domains: list[str] = Field(default_factory=list, max_length=20)


class CollegeProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    registration_number: str = Field(min_length=3, max_length=24)


class CollegeProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str
    email: str
    phone: str | None
    registration_number: str | None
    vehicle_type: VehicleType | None


class CollegeSlotRead(BaseModel):
    slot_id: int
    code: str
    status: str


class CollegeFacilityRead(BaseModel):
    id: int
    name: str
    address: str
    latitude: float | None
    longitude: float | None
    timezone: str
    capacity: int
    occupied: int
    available: int
    last_updated: datetime
    slots: list[CollegeSlotRead]


class CollegeSessionRead(BaseModel):
    id: int
    ticket_id: str
    student_name: str
    phone: str | None = None
    vehicle_number: str
    space: str
    entry_source: str | None
    exit_source: str | None
    entry_time: datetime
    exit_time: datetime | None
    duration_minutes: int | None
    status: ParkingSessionStatus


class CollegeActionResponse(BaseModel):
    session: CollegeSessionRead
    facility: CollegeFacilityRead


class CollegeQrRead(BaseModel):
    entry_path: str
    exit_path: str


class AdminManualEntry(BaseModel):
    user_id: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=500)


class AdminManualExit(BaseModel):
    ticket_id: str = Field(min_length=8, max_length=64)
    reason: str = Field(min_length=3, max_length=500)

