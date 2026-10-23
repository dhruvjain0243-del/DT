"""Add college parking configuration and explicit session sources."""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_college_parking"
down_revision: str | None = "0003_scanner_api_keys"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("facilities", sa.Column("timezone", sa.String(64), nullable=True))
    op.add_column("facilities", sa.Column("permitted_email_domains", sa.Text(), nullable=True))
    op.execute("UPDATE facilities SET timezone = 'Asia/Kolkata' WHERE timezone IS NULL")
    # SQLite cannot alter a column's nullability with ALTER TABLE. Existing rows
    # are populated above; the ORM default covers new rows on supported databases.
    op.add_column("parking_sessions", sa.Column("entry_source", sa.String(32), nullable=True))
    op.add_column("parking_sessions", sa.Column("exit_source", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("parking_sessions", "exit_source")
    op.drop_column("parking_sessions", "entry_source")
    op.drop_column("facilities", "permitted_email_domains")
    op.drop_column("facilities", "timezone")
