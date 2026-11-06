"""Migrate additively and verify recovery in a rolled-back PostgreSQL schema; never send mail."""
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision in {"20261104_0006", "20261105_0007", "20261105_0008", "20261105_0009", "20261105_0010", "20261105_0011", "20261106_0012", "20261106_0013"}, "Unexpected migration revision"
        old_tables = sorted(set(inspect(connection).get_table_names()) & set(Base.metadata.tables))
        counts = {name: connection.scalar(text(f'SELECT COUNT(*) FROM "{name}"')) for name in old_tables}
        users = connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert not compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
        assert counts == {name: connection.scalar(text(f'SELECT COUNT(*) FROM "{name}"')) for name in old_tables}
        assert users == connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
    print("Current migration head verified; existing row counts and login accounts preserved.")

    schema = "qa_recovery_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        db = None
        try:
            connection.exec_driver_sql("CREATE SCHEMA " + schema)
            connection.exec_driver_sql("SET LOCAL search_path TO " + schema)
            Base.metadata.create_all(connection, checkfirst=False)
            factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
            db = factory()
            db.add(User(email="qa@example.test", name="QA Owner", role="Admin", is_owner=True, admin_slot=1, password_hash=passwords.hash("QaOld123")))
            db.commit()
            app.dependency_overrides[get_db] = lambda: db
            messages = []
            with patch.object(settings, "PASSWORD_RECOVERY_ENABLED", True), patch("app.services.password_recovery.SessionLocal", factory), patch("app.services.request_limits.SessionLocal", factory), patch("app.services.password_recovery.send_reset_message", side_effect=lambda *args: messages.append(args)), TestClient(app, headers={"X-CRM-Request": "1"}) as client:
                login = client.post("/api/auth/login", json={"email": "qa@example.test", "password": "QaOld123"})
                assert login.status_code == 200
                assert client.post("/api/auth/forgot-password", json={"email": "qa@example.test"}).status_code == 202
                token = parse_qs(urlsplit(messages[0][1]).fragment.split("?", 1)[1])["token"][0]
                reset = {"token": token, "newPassword": "QaNew123"}
                assert client.post("/api/auth/reset-password", json=reset).status_code == 204
                assert client.post("/api/auth/reset-password", json=reset).status_code == 400
                assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + login.json()["accessToken"]}).status_code == 401
                assert client.post("/api/auth/login", json={"email": "qa@example.test", "password": "QaNew123"}).status_code == 200
        finally:
            app.dependency_overrides.clear()
            if db:
                db.close()
            transaction.rollback()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}) == 0
    engine.dispose()
    print("PostgreSQL recovery, replay prevention and session revocation passed; QA schema rolled back; SMTP mocked.")


if __name__ == "__main__":
    main()
