from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ..models.enums import UserRole, VehicleType


PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{12,128}$")
REGISTRATION_PATTERN = re.compile(r"^[A-Z0-9]{5,15}$")


def normalize_registration(value: str) -> str:
    normalized = re.sub(r"[\s-]", "", value).upper()
    if not REGISTRATION_PATTERN.fullmatch(normalized):
        raise ValueError("Registration number must contain 5-15 letters or digits")
    return normalized


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    college_id: str | None = Field(default=None, min_length=2, max_length=80)
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    password: str = Field(min_length=12, max_length=128)
    role: UserRole = UserRole.STUDENT

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not PASSWORD_PATTERN.fullmatch(value):
            raise ValueError(
                "Password must be at least 12 characters and include uppercase, "
                "lowercase, number, and symbol"
            )
        return value

    @field_validator("role")
    @classmethod
    def public_role(cls, value: UserRole) -> UserRole:
        if value not in {UserRole.STUDENT, UserRole.STAFF, UserRole.VISITOR}:
            raise ValueError("Public registration supports STUDENT, STAFF, or VISITOR")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    college_id: str | None
    phone: str | None
    role: UserRole
    is_active: bool
    created_at: datetime


class UserAdminUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class VehicleCreate(BaseModel):
    registration_number: str
    vehicle_type: VehicleType

    @field_validator("registration_number")
    @classmethod
    def registration_is_valid(cls, value: str) -> str:
        return normalize_registration(value)


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    registration_number: str
    vehicle_type: VehicleType
    created_at: datetime
