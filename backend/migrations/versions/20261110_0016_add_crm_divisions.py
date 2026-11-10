"""Add ENGEN, Visotonics and Overview divisions to shared settings."""
import json

from alembic import op
import sqlalchemy as sa


revision = "20261110_0016"
down_revision = "20261106_0015"
branch_labels = None
depends_on = None


DIVISIONS = {
    "MMC": {"name": "MMC", "address": "", "gst": "", "prefix": "MMC"},
    "nemilink": {"name": "nemilink", "address": "", "gst": "", "prefix": "NEM"},
    "ClearCode Labs": {"name": "ClearCode Labs", "address": "", "gst": "", "prefix": "CCL"},
    "ENGEN": {"name": "ENGEN", "address": "", "gst": "", "prefix": "ENG"},
    "Visotonics": {"name": "Visotonics", "address": "", "gst": "", "prefix": "VIS"},
    "Overview": {"name": "Overview", "address": "", "gst": "", "prefix": "OVW"},
}


def upgrade():
    connection = op.get_bind()
    settings = sa.Table(
        "workspace_settings",
        sa.MetaData(),
        sa.Column("id", sa.Integer),
        sa.Column("data", sa.JSON),
        sa.Column("version", sa.Integer),
    )
    for row in connection.execute(sa.select(settings.c.id, settings.c.data, settings.c.version)).mappings():
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data or {})
        divisions = dict(data.get("divisions") or {})
        changed = False
        for name, defaults in DIVISIONS.items():
            if name not in divisions:
                divisions[name] = defaults
                changed = True
        if changed:
            data["divisions"] = divisions
            connection.execute(
                settings.update().where(settings.c.id == row["id"]).values(
                    data=data,
                    version=row["version"] + 1,
                )
            )


def downgrade():
    # Division values may already be referenced by CRM records; retain them.
    pass
