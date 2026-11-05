"""Versions for lead/customer edits; stable list ordering indexes."""
from alembic import op
import sqlalchemy as sa

revision = "20261105_0010"
down_revision = "20261105_0009"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("leads", "customers"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    for table, field in (("leads", "created_at"), ("customers", "created_at"), ("quotations", "created_at"), ("follow_ups", "due_at")):
        op.create_index(f"ix_{table}_list_order", table, [field, "id"])


def downgrade():
    for table, _ in (("leads", "created_at"), ("customers", "created_at"), ("quotations", "created_at"), ("follow_ups", "due_at")):
        op.drop_index(f"ix_{table}_list_order", table_name=table)
    for table in ("customers", "leads"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("version")
