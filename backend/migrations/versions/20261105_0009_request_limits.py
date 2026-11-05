"""Shared login and API request budgets."""
from alembic import op
import sqlalchemy as sa

revision = "20261105_0009"
down_revision = "20261105_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rate_limit_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False))
    op.create_index("ix_rate_limit_buckets_window_started_at", "rate_limit_buckets", ["window_started_at"])


def downgrade():
    op.drop_index("ix_rate_limit_buckets_window_started_at", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
