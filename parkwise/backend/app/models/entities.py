from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .enums import (
    EntryMethod,
    FeedbackCategory,
    FeedbackStatus,
    ParkingSessionStatus,
    SlotStatus,
    UserRole,
    VehicleType,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_type: type, name: str) -> SAEnum:
    return SAEnum(
        enum_type,
        name=name,
        native_enum=False,
        values_callable=lambda enum: [item.value for item in enum],
        validate_strings=True,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    college_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "user_role"), default=UserRole.STUDENT, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    vehicles: Mapped[list[Vehicle]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    parking_sessions: Mapped[list[ParkingSession]] = relationship(back_populates="user")
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="user")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    registration_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(enum_column(VehicleType, "vehicle_type"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="vehicles")
    parking_sessions: Mapped[list[ParkingSession]] = relationship(back_populates="vehicle")


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (CheckConstraint("total_capacity > 0", name="ck_facility_capacity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    address: Mapped[str] = mapped_column(Text)
    total_capacity: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    price_per_hour: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    zones: Mapped[list[ParkingZone]] = relationship(
        back_populates="facility", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[ParkingSession]] = relationship(back_populates="facility")
    predictions: Mapped[list[Prediction]] = relationship(back_populates="facility")


class ParkingZone(Base):
    __tablename__ = "parking_zones"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_zone_capacity_positive"),
        UniqueConstraint("facility_id", "name", name="uq_zone_facility_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    vehicle_type: Mapped[VehicleType] = mapped_column(enum_column(VehicleType, "zone_vehicle_type"), index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    facility: Mapped[Facility] = relationship(back_populates="zones")
    slots: Mapped[list[ParkingSlot]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[ParkingSession]] = relationship(back_populates="zone")
    predictions: Mapped[list[Prediction]] = relationship(back_populates="zone")


class ParkingSlot(Base):
    __tablename__ = "parking_slots"
    __table_args__ = (
        UniqueConstraint("zone_id", "slot_code", name="uq_slot_zone_code"),
        Index("ix_slots_zone_status", "zone_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("parking_zones.id", ondelete="CASCADE"), index=True
    )
    row_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    slot_code: Mapped[str] = mapped_column(String(60))
    status: Mapped[SlotStatus] = mapped_column(
        enum_column(SlotStatus, "slot_status"), default=SlotStatus.AVAILABLE, index=True
    )
    qr_code_value: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    zone: Mapped[ParkingZone] = relationship(back_populates="slots")
    sessions: Mapped[list[ParkingSession]] = relationship(back_populates="slot")


class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    __table_args__ = (
        CheckConstraint(
            "(status = 'ACTIVE' AND exit_time IS NULL) OR "
            "(status = 'COMPLETED' AND exit_time IS NOT NULL) OR status = 'CANCELLED'",
            name="ck_session_status_exit_time",
        ),
        Index("ix_sessions_ticket", "ticket_id", unique=True),
        Index(
            "uq_active_session_vehicle",
            "vehicle_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uq_active_session_slot",
            "slot_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_sessions_facility_status", "facility_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("parking_zones.id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("parking_slots.id"), index=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ParkingSessionStatus] = mapped_column(
        enum_column(ParkingSessionStatus, "parking_session_status"),
        default=ParkingSessionStatus.ACTIVE,
        index=True,
    )
    entry_method: Mapped[EntryMethod] = mapped_column(enum_column(EntryMethod, "entry_method"))
    exit_method: Mapped[EntryMethod | None] = mapped_column(
        enum_column(EntryMethod, "exit_method"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="parking_sessions")
    vehicle: Mapped[Vehicle] = relationship(back_populates="parking_sessions")
    facility: Mapped[Facility] = relationship(back_populates="sessions")
    zone: Mapped[ParkingZone] = relationship(back_populates="sessions")
    slot: Mapped[ParkingSlot] = relationship(back_populates="sessions")
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="session")


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "reported_available_spaces IS NULL OR reported_available_spaces >= 0",
            name="ck_feedback_reported_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("parking_sessions.id"), nullable=True, index=True
    )
    category: Mapped[FeedbackCategory] = mapped_column(
        enum_column(FeedbackCategory, "feedback_category"), index=True
    )
    description: Mapped[str] = mapped_column(Text)
    reported_available_spaces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[FeedbackStatus] = mapped_column(
        enum_column(FeedbackStatus, "feedback_status"), default=FeedbackStatus.OPEN, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="feedback_items")
    session: Mapped[ParkingSession | None] = relationship(back_populates="feedback_items")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("predicted_available_spaces >= 0", name="ck_prediction_nonnegative"),
        Index("ix_predictions_facility_time", "facility_id", "prediction_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("parking_zones.id"), nullable=True, index=True
    )
    prediction_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    target_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    predicted_available_spaces: Mapped[int] = mapped_column(Integer)
    actual_available_spaces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_version: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    facility: Mapped[Facility] = relationship(back_populates="predictions")
    zone: Mapped[ParkingZone | None] = relationship(back_populates="predictions")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_actor_created", "actor_user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
