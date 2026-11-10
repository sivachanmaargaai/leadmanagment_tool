"""Align databases that applied the older 100-character lead customer migration."""
from alembic import op
import sqlalchemy as sa

revision = "20261106_0015"
down_revision = "20261106_0014"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    current = next(column["type"] for column in sa.inspect(connection).get_columns("leads") if column["name"] == "customer")
    if getattr(current, "length", None) == 120:
        return
    with op.batch_alter_table("leads") as batch:
        batch.alter_column("customer", existing_type=current, type_=sa.String(120), existing_nullable=False)


def downgrade():
    # 0011 already specifies 120. Keep its canonical schema when rolling back
    # this drift repair; 0011's own guarded downgrade handles shrinking to 100.
    pass
