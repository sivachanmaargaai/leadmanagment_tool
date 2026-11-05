"""Initial Lead and Customer schema. Existing installations must verify and baseline first."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer", sa.String(100), nullable=False),
        sa.Column("contact", sa.String(150), nullable=False),
        sa.Column("division", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("lead_source", sa.String(100), nullable=False),
        sa.Column("referred_by", sa.JSON(), nullable=True),
        sa.Column("reference_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("divisions", sa.JSON(), nullable=False),
        sa.Column("contacts", sa.JSON(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("postcode", sa.String(20), nullable=False),
        sa.Column("gst", sa.String(30), nullable=False),
        sa.Column("assigned_to", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("lead_source", sa.String(100), nullable=False),
        sa.Column("referred_by", sa.JSON(), nullable=True),
        sa.Column("reference_notes", sa.Text(), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_customers_name", "customers", ["name"])


def downgrade():
    op.drop_index("ix_customers_name", table_name="customers")
    op.drop_table("customers")
    op.drop_table("leads")
