"""First administrator owns account management; enforce two admin slots."""
from alembic import op
import sqlalchemy as sa

revision = "20261104_0005"
down_revision = "20261104_0004"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    admins = connection.execute(sa.text("SELECT id FROM users WHERE role = 'Admin' ORDER BY created_at, id")).scalars().all()
    if len(admins) > 2:
        raise RuntimeError("More than two administrators exist. Review accounts before applying this migration.")
    op.add_column("users", sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("admin_slot", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    for index, user_id in enumerate(admins):
        if index == 0:
            active = connection.execute(sa.text("SELECT is_active FROM users WHERE id = :id"), {"id": user_id}).scalar()
            if not active:
                raise RuntimeError("The first administrator is inactive. Review the owner account before migration.")
        connection.execute(sa.text("UPDATE users SET admin_slot=:slot, is_owner=:owner WHERE id=:id"),
                           {"slot": index + 1, "owner": index == 0, "id": user_id})
    with op.batch_alter_table("users") as batch:
        batch.create_unique_constraint("uq_user_admin_slot", ["admin_slot"])
        batch.create_check_constraint("ck_user_admin_slot", "(role = 'Admin' AND admin_slot IS NOT NULL AND admin_slot IN (1, 2)) OR (role = 'Staff' AND admin_slot IS NULL)")
        batch.create_check_constraint("ck_user_owner_active", "NOT is_owner OR (role = 'Admin' AND admin_slot = 1 AND is_active)")
        batch.create_check_constraint("ck_user_owner_slot", "admin_slot IS NULL OR admin_slot <> 1 OR is_owner")
        batch.alter_column("is_owner", existing_type=sa.Boolean(), server_default=None)
        batch.alter_column("version", existing_type=sa.Integer(), server_default=None)
    op.create_table("user_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_user_audit_events_target_id", "user_audit_events", ["target_id"])


def downgrade():
    op.drop_index("ix_user_audit_events_target_id", table_name="user_audit_events")
    op.drop_table("user_audit_events")
    with op.batch_alter_table("users") as batch:
        for name in ["ck_user_owner_slot", "ck_user_owner_active", "ck_user_admin_slot"]:
            batch.drop_constraint(name, type_="check")
        batch.drop_constraint("uq_user_admin_slot", type_="unique")
        batch.drop_column("version")
        batch.drop_column("admin_slot")
        batch.drop_column("is_owner")
