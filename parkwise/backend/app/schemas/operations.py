from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import GateType, ScanResult, ScanType


class GateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    gate_type: GateType = GateType.BOTH
    is_active: bool = True


class GateRead(GateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    facility_id: int
    created_at: datetime


class ScannerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    device_identifier: str = Field(min_length=3, max_length=160)
    is_active: bool = True


class ScannerRead(ScannerCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gate_id: int
    last_seen_at: datetime | None
    created_at: datetime


class ScannerProvisioned(ScannerRead):
    api_key: str


class ScannerActionResponse(ScannerRead):
    message: str


class ScannerScanRequest(BaseModel):
    scan_type: ScanType
    qr_token: str | None = Field(default=None, min_length=20)
    vehicle_registration: str | None = Field(default=None, min_length=3, max_length=24)
    scan_reference: str | None = Field(default=None, max_length=160)


class ScanEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    facility_id: int
    gate_id: int
    scanner_device_id: int | None
    actor_user_id: int | None
    session_id: int | None
    scan_type: ScanType
    result: ScanResult
    reference: str | None
    failure_reason: str | None
    scanned_at: datetime
