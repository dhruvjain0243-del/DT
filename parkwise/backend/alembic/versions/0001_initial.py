"""Initial PARKWISE schema.

Revision ID: 0001_initial
Revises: None
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("college_id", sa.String(80), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("ADMIN", "ATTENDANT", "STUDENT", "STAFF", "VISITOR", name="user_role", native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("college_id"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("total_capacity", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=False, server_default="0"),
        sa.Column("price_per_hour", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("total_capacity > 0", name="ck_facility_capacity_positive"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_facilities_name", "facilities", ["name"])
    op.create_index("ix_facilities_is_active", "facilities", ["is_active"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registration_number", sa.String(24), nullable=False),
        sa.Column("vehicle_type", sa.Enum("CAR", "MOTORCYCLE", "BICYCLE", "VAN", "EV", "ACCESSIBLE", name="vehicle_type", native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("registration_number"),
    )
    op.create_index("ix_vehicles_user_id", "vehicles", ["user_id"])
    op.create_index("ix_vehicles_registration_number", "vehicles", ["registration_number"])

    op.create_table(
        "parking_zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("vehicle_type", sa.Enum("CAR", "MOTORCYCLE", "BICYCLE", "VAN", "EV", "ACCESSIBLE", name="zone_vehicle_type", native_enum=False), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("capacity > 0", name="ck_zone_capacity_positive"),
        sa.UniqueConstraint("facility_id", "name", name="uq_zone_facility_name"),
    )
    op.create_index("ix_parking_zones_facility_id", "parking_zones", ["facility_id"])
    op.create_index("ix_parking_zones_vehicle_type", "parking_zones", ["vehicle_type"])
    op.create_index("ix_parking_zones_is_active", "parking_zones", ["is_active"])

    op.create_table(
        "parking_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("parking_zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_label", sa.String(30), nullable=True),
        sa.Column("slot_code", sa.String(60), nullable=False),
        sa.Column("status", sa.Enum("AVAILABLE", "OCCUPIED", "RESERVED", "OUT_OF_SERVICE", name="slot_status", native_enum=False), nullable=False),
        sa.Column("qr_code_value", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("zone_id", "slot_code", name="uq_slot_zone_code"),
        sa.UniqueConstraint("qr_code_value"),
    )
    op.create_index("ix_parking_slots_zone_id", "parking_slots", ["zone_id"])
    op.create_index("ix_parking_slots_status", "parking_slots", ["status"])
    op.create_index("ix_parking_slots_is_active", "parking_slots", ["is_active"])
    op.create_index("ix_slots_zone_status", "parking_slots", ["zone_id", "status"])

    op.create_table(
        "parking_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("parking_zones.id"), nullable=False),
        sa.Column("slot_id", sa.Integer(), sa.ForeignKey("parking_slots.id"), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("ACTIVE", "COMPLETED", "CANCELLED", name="parking_session_status", native_enum=False), nullable=False),
        sa.Column("entry_method", sa.Enum("QR", "MANUAL", "SELF_SERVICE", name="entry_method", native_enum=False), nullable=False),
        sa.Column("exit_method", sa.Enum("QR", "MANUAL", "SELF_SERVICE", name="exit_method", native_enum=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("(status = 'ACTIVE' AND exit_time IS NULL) OR (status = 'COMPLETED' AND exit_time IS NOT NULL) OR status = 'CANCELLED'", name="ck_session_status_exit_time"),
    )
    for column in ("user_id", "vehicle_id", "facility_id", "zone_id", "slot_id", "entry_time", "status"):
        op.create_index(f"ix_parking_sessions_{column}", "parking_sessions", [column])
    op.create_index("ix_sessions_ticket", "parking_sessions", ["ticket_id"], unique=True)
    op.create_index("ix_sessions_facility_status", "parking_sessions", ["facility_id", "status"])
    op.create_index("uq_active_session_vehicle", "parking_sessions", ["vehicle_id"], unique=True, sqlite_where=sa.text("status = 'ACTIVE'"), postgresql_where=sa.text("status = 'ACTIVE'"))
    op.create_index("uq_active_session_slot", "parking_sessions", ["slot_id"], unique=True, sqlite_where=sa.text("status = 'ACTIVE'"), postgresql_where=sa.text("status = 'ACTIVE'"))

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("parking_sessions.id"), nullable=True),
        sa.Column("category", sa.Enum("AVAILABILITY", "SAFETY", "CLEANLINESS", "ACCESSIBILITY", "OTHER", name="feedback_category", native_enum=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reported_available_spaces", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum("OPEN", "REVIEWED", "RESOLVED", name="feedback_status", native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("reported_available_spaces IS NULL OR reported_available_spaces >= 0", name="ck_feedback_reported_nonnegative"),
    )
    for column in ("user_id", "session_id", "category", "status"):
        op.create_index(f"ix_feedback_{column}", "feedback", [column])

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("parking_zones.id"), nullable=True),
        sa.Column("prediction_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_available_spaces", sa.Integer(), nullable=False),
        sa.Column("actual_available_spaces", sa.Integer(), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("predicted_available_spaces >= 0", name="ck_prediction_nonnegative"),
    )
    for column in ("facility_id", "zone_id", "prediction_time", "target_time", "model_version"):
        op.create_index(f"ix_predictions_{column}", "predictions", [column])
    op.create_index("ix_predictions_facility_time", "predictions", ["facility_id", "prediction_time"])

    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("jti"),
    )
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"])
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("actor_user_id", "action", "entity_type", "created_at"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])
    op.create_index("ix_audit_actor_created", "audit_logs", ["actor_user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("revoked_tokens")
    op.drop_table("predictions")
    op.drop_table("feedback")
    op.drop_table("parking_sessions")
    op.drop_table("parking_slots")
    op.drop_table("parking_zones")
    op.drop_table("vehicles")
    op.drop_table("facilities")
    op.drop_table("users")
