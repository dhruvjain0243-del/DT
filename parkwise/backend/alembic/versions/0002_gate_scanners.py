"""Add physical gate, scanner, and scan-event tracking."""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_gate_scanners"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parking_gates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("gate_type", sa.Enum("ENTRY", "EXIT", "BOTH", name="gate_type", native_enum=False), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("facility_id", "name", name="uq_gate_facility_name"),
    )
    op.create_index("ix_parking_gates_facility_id", "parking_gates", ["facility_id"])
    op.create_index("ix_parking_gates_is_active", "parking_gates", ["is_active"])

    op.create_table(
        "scanner_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gate_id", sa.Integer(), sa.ForeignKey("parking_gates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("device_identifier", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("device_identifier", name="uq_scanner_device_identifier"),
    )
    op.create_index("ix_scanner_devices_gate_id", "scanner_devices", ["gate_id"])
    op.create_index("ix_scanner_devices_is_active", "scanner_devices", ["is_active"])

    op.create_table(
        "scan_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facility_id", sa.Integer(), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("gate_id", sa.Integer(), sa.ForeignKey("parking_gates.id"), nullable=False),
        sa.Column("scanner_device_id", sa.Integer(), sa.ForeignKey("scanner_devices.id"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("parking_sessions.id"), nullable=True),
        sa.Column("scan_type", sa.Enum("ENTRY", "EXIT", name="scan_type", native_enum=False), nullable=False),
        sa.Column("result", sa.Enum("SUCCESS", "FAILED", name="scan_result", native_enum=False), nullable=False),
        sa.Column("reference", sa.String(160), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("facility_id", "gate_id", "scanner_device_id", "actor_user_id", "session_id", "scan_type", "result", "scanned_at"):
        op.create_index(f"ix_scan_events_{column}", "scan_events", [column])
    op.create_index("ix_scan_events_facility_time", "scan_events", ["facility_id", "scanned_at"])
    op.create_index("ix_scan_events_result_time", "scan_events", ["result", "scanned_at"])


def downgrade() -> None:
    op.drop_table("scan_events")
    op.drop_table("scanner_devices")
    op.drop_table("parking_gates")
