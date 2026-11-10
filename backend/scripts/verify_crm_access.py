"""Apply assignment migration without changing accounts; run rolled-back PostgreSQL access checks."""
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.role_permissions import RolePermissions
from app.models.user import User


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        old = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert old in {"20261105_0007", "20261105_0008", "20261105_0009", "20261105_0010", "20261105_0011", "20261106_0012", "20261106_0013", "20261106_0014", "20261106_0015", "20261110_0016", "20261110_0017"}, "Unexpected migration revision"
        existing = set(inspect(connection).get_table_names()) & set(Base.metadata.tables)
        counts = {name: connection.scalar(text(f'SELECT COUNT(*) FROM "{name}"')) for name in existing}
        users = connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert not compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
        assert counts == {name: connection.scalar(text(f'SELECT COUNT(*) FROM "{name}"')) for name in existing}
        assert users == connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        if old == "20261105_0007":
            for table in ("leads", "customers", "quotations"):
                assert connection.scalar(text(f'SELECT COUNT(*) FROM "{table}" WHERE assignee_user_id IS NOT NULL')) == 0
    print("Current migration head matches models; existing accounts, record counts and assignments preserved.")

    schema = "qa_access_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        db = None
        try:
            connection.exec_driver_sql("CREATE SCHEMA " + schema)
            connection.exec_driver_sql("SET LOCAL search_path TO " + schema)
            Base.metadata.create_all(connection, checkfirst=False)
            factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
            db = factory()
            hashed = passwords.hash("QaAccess123")
            users = [User(email=f"qa{n}@example.test", name="Duplicate name", role="Admin" if n == 0 else "Staff", quotation_access=n != 0,
                          is_owner=n == 0, admin_slot=1 if n == 0 else None, password_hash=hashed) for n in range(3)]
            db.add(RolePermissions(role="Staff", quotations=True))
            db.add_all(users)
            db.commit()
            app.dependency_overrides[get_db] = lambda: db
            with patch("app.services.request_limits.SessionLocal", factory), TestClient(app, headers={"X-CRM-Request": "1"}) as client:
                headers = []
                for user in users:
                    response = client.post("/api/auth/login", json={"email": user.email, "password": "QaAccess123"})
                    assert response.status_code == 200
                    headers.append({"Authorization": "Bearer " + response.json()["accessToken"]})
                client.headers.update(headers[0])
                lead_response = client.post("/api/leads", json={"customer": "PostgreSQL access QA", "division": "MMC", "description": "Embedded"})
                assert lead_response.status_code == 201
                lead = lead_response.json()
                assert client.get("/api/leads", headers=headers[1]).json() == []
                path = "/api/access/assignments/leads/" + lead["id"]
                payload = {"assigneeUserId": users[1].id, "expectedAssigneeUserId": lead["assigneeUserId"], "expectedVersion": 1}
                assert client.put(path, json=payload).status_code == 200
                assert client.get("/api/leads/" + lead["id"], headers=headers[1]).status_code == 200
                assert client.get("/api/leads/" + lead["id"], headers=headers[2]).status_code == 404
                assert client.put("/api/leads/" + lead["id"], headers=headers[2], json={"priority": "High"}).status_code == 404
                assert client.delete("/api/leads/" + lead["id"], headers=headers[1]).status_code == 403
                assert client.get("/api/reports/summary", headers=headers[1]).json()["totals"]["totalLeads"] == 1
                assert client.get("/api/reports/summary", headers=headers[2]).json()["totals"]["totalLeads"] == 0
                payload = {"assigneeUserId": users[2].id, "expectedAssigneeUserId": users[1].id, "expectedVersion": 2}
                assert client.put(path, headers=headers[1], json=payload).status_code == 403
                assert client.put(path, json=payload).status_code == 200
                assert client.get("/api/leads/" + lead["id"], headers=headers[1]).status_code == 404
                assert client.get("/api/leads/" + lead["id"], headers=headers[2]).status_code == 200
                assert client.put(path, json=payload).status_code == 409
        finally:
            app.dependency_overrides.clear()
            if db:
                db.close()
            transaction.rollback()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}) == 0
    engine.dispose()
    print("PostgreSQL Staff isolation, direct requests, reports, reassignment and conflicts passed. QA schema rolled back.")


if __name__ == "__main__":
    main()
