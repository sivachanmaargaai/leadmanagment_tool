"""Normalize the historical Nemilinks division typo."""
from alembic import op
import sqlalchemy as sa


revision = "20261110_0017"
down_revision = "20261110_0016"
branch_labels = None
depends_on = None


def upgrade():
    # Follow-ups inherit their division from the linked lead, so fixing the
    # lead rows also fixes follow-up response validation without editing tasks.
    leads = sa.table("leads", sa.column("division", sa.String(100)))
    op.execute(
        leads.update()
        .where(leads.c.division == "Nemilinks")
        .values(division="nemilink")
    )


def downgrade():
    # Keep normalized records canonical; reverting would reintroduce invalid
    # division values and break API response validation.
    pass
