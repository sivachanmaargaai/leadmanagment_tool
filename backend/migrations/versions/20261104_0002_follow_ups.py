"""Add lead-linked follow-ups and retained history."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0002"
down_revision = "20261104_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("follow_ups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lead_id", sa.String(36), sa.ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purpose", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_to", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("reminder_minutes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("completion_notes", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    for field in ["lead_id", "due_at", "status"]:
        op.create_index(f"ix_follow_ups_{field}", "follow_ups", [field])


def downgrade():
    for field in ["status", "due_at", "lead_id"]:
        op.drop_index(f"ix_follow_ups_{field}", table_name="follow_ups")
    op.drop_table("follow_ups")
