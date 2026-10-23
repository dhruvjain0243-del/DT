"""Track verified email ownership for password login."""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_email_verification"
down_revision: str | None = "0004_college_parking"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=True))
    # Existing accounts were created under the previous password-login contract.
    # New registrations default to unverified and must confirm ownership.
    op.execute("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL")


def downgrade() -> None:
    op.drop_column("users", "email_verified")
