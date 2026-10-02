"""Add hashed API credentials for scanner devices."""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_scanner_api_keys"
down_revision: str | None = "0002_gate_scanners"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("scanner_devices", sa.Column("api_key_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("scanner_devices", "api_key_hash")
