"""Retain quotations and immutable PDF revisions in the database."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0003"
down_revision = "20261104_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("quotations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("number_key", sa.String(50), nullable=False),
        sa.Column("division", sa.String(100), nullable=False),
        sa.Column("customer", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("division", "number_key", name="uq_quotation_division_number"))
    op.create_index("ix_quotations_customer", "quotations", ["customer"])
    op.create_table("quotation_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("quotation_id", sa.String(36), sa.ForeignKey("quotations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("quotation_id", "revision", name="uq_quotation_file_revision"))
    op.create_index("ix_quotation_files_quotation_id", "quotation_files", ["quotation_id"])


def downgrade():
    op.drop_index("ix_quotation_files_quotation_id", table_name="quotation_files")
    op.drop_table("quotation_files")
    op.drop_index("ix_quotations_customer", table_name="quotations")
    op.drop_table("quotations")
