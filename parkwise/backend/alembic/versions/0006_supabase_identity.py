"""Link PARKWISE users to Supabase Auth identities."""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_supabase_identity"
down_revision: str | None = "0005_email_verification"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("supabase_user_id", sa.String(100), nullable=True))
    op.create_index("ix_users_supabase_user_id", "users", ["supabase_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_supabase_user_id", table_name="users")
    op.drop_column("users", "supabase_user_id")
