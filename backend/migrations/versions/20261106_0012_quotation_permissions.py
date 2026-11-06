"""Staff quotation access defaults off; administrators retain implicit access."""
from alembic import op
import sqlalchemy as sa

revision = "20261106_0012"
down_revision = "20261105_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("quotation_access", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("quotation_access")
