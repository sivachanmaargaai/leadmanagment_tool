"""Common Staff policy replaces individual quotation grants; starts disabled."""
from alembic import op
import sqlalchemy as sa

revision = "20261106_0013"
down_revision = "20261106_0012"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table("role_permissions",
        sa.Column("role", sa.String(20), primary_key=True),
        sa.Column("quotations", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.bulk_insert(table, [{"role": "Staff", "quotations": False, "version": 1}])
    # Existing individual grants no longer apply. Refresh Staff UI/auth state;
    # administrator sessions and account/password fields remain unchanged.
    op.execute(sa.text("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE revoked_at IS NULL AND user_id IN (SELECT id FROM users WHERE role='Staff')"))


def downgrade():
    op.drop_table("role_permissions")
