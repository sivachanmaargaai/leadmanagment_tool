"""Persist shared business settings and individual user preferences."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0006"
down_revision = "20261104_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_workspace_settings_singleton"))
    # An empty JSON object resolves to the versioned application defaults.
    op.execute(sa.text("INSERT INTO workspace_settings (id,data,version,updated_at) VALUES (1,'{}',1,CURRENT_TIMESTAMP)"))
    op.create_table("user_preferences",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("user_preferences")
    op.drop_table("workspace_settings")
