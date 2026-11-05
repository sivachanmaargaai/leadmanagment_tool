"""Stable user assignments; legacy records remain Admin-only until reviewed."""
from alembic import op
import sqlalchemy as sa

revision = "20261105_0008"
down_revision = "20261105_0007"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("leads", "customers", "quotations"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("assignee_user_id", sa.String(36), nullable=True))
            batch.create_foreign_key(f"fk_{table}_assignee", "users", ["assignee_user_id"], ["id"], ondelete="RESTRICT")
            batch.create_index(f"ix_{table}_assignee_user_id", ["assignee_user_id"])


def downgrade():
    for table in ("quotations", "customers", "leads"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_assignee_user_id")
            batch.drop_constraint(f"fk_{table}_assignee", type_="foreignkey")
            batch.drop_column("assignee_user_id")
