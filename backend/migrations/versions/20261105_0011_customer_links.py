"""Stable customer foreign keys and conservative legacy backfill."""
from collections import defaultdict
from alembic import op
import sqlalchemy as sa

revision = "20261105_0011"
down_revision = "20261105_0010"
branch_labels = None
depends_on = None


def key(value):
    return " ".join((value or "").casefold().split())


def upgrade():
    for name in ("leads", "quotations"):
        with op.batch_alter_table(name) as batch:
            if name == "leads":
                batch.alter_column("customer", existing_type=sa.String(100), type_=sa.String(120), existing_nullable=False)
            batch.add_column(sa.Column("customer_id", sa.String(36), nullable=True))
            batch.create_foreign_key(f"fk_{name}_customer", "customers", ["customer_id"], ["id"], ondelete="RESTRICT")
            batch.create_index(f"ix_{name}_customer_id", ["customer_id"])
    connection = op.get_bind()
    customers = sa.table("customers", sa.column("id"), sa.column("name"), sa.column("aliases", sa.JSON))
    names = defaultdict(set)
    for row in connection.execute(sa.select(customers)).mappings():
        for name in [row["name"], *(row["aliases"] or [])]:
            if key(name):
                names[key(name)].add(row["id"])
    # Stream records; match globally, never choose between duplicate names/aliases.
    for name in ("leads", "quotations"):
        table = sa.table(name, sa.column("id"), sa.column("customer"), sa.column("customer_id"), sa.column("version"))
        cursor = ""
        while True:
            rows = connection.execute(sa.select(table.c.id, table.c.customer).where(table.c.id > cursor).order_by(table.c.id).limit(500)).all()
            if not rows:
                break
            for row in rows:
                matches = names.get(key(row.customer), set())
                if len(matches) == 1:
                    connection.execute(table.update().where(table.c.id == row.id).values(customer_id=next(iter(matches)), version=table.c.version + 1))
            cursor = rows[-1].id


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT count(*) FROM leads WHERE length(customer) > 100")):
        raise RuntimeError("Cannot downgrade: some lead names exceed the old 100-character limit")
    for name in ("quotations", "leads"):
        with op.batch_alter_table(name) as batch:
            batch.drop_index(f"ix_{name}_customer_id")
            batch.drop_constraint(f"fk_{name}_customer", type_="foreignkey")
            batch.drop_column("customer_id")
            if name == "leads":
                batch.alter_column("customer", existing_type=sa.String(120), type_=sa.String(100), existing_nullable=False)
