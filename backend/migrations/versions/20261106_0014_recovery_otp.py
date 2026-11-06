"""Add email OTP challenges without changing users or existing reset links."""
from alembic import op
import sqlalchemy as sa

revision = "20261106_0014"
down_revision = "20261106_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("password_reset_tokens", sa.Column("recovery_kind", sa.String(8), nullable=False, server_default="link"))
    op.add_column("password_reset_tokens", sa.Column("otp_hash", sa.String(64), nullable=True))
    op.add_column("password_reset_tokens", sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("password_reset_tokens", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    for name in ("verified_at", "failed_attempts", "otp_hash", "recovery_kind"):
        op.drop_column("password_reset_tokens", name)
