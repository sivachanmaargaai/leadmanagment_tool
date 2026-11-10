"""Migrate additively and verify recovery in a rolled-back PostgreSQL schema; never send mail."""
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import re

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


def verify_concurrent_otp(engine):
    """Independent transactions exercise real PostgreSQL row locks; never use real accounts."""
    schema = "qa_otp_races_" + uuid4().hex
    assert re.fullmatch(r"qa_otp_races_[a-f0-9]{32}", schema)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA " + schema)
    qa = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10,
        "options": "-csearch_path=" + schema + " -cstatement_timeout=15000"}, hide_parameters=True)
    try:
        Base.metadata.create_all(qa, checkfirst=False)
        factory = sessionmaker(bind=qa)
        with factory() as db:
            user = User(email="race@example.test", name="QA Staff", role="Staff", password_hash=passwords.hash("QaOld123"))
            db.add(user)
            db.commit()
            user_id = user.id

        def dependency():
            with factory() as db:
                yield db

        app.dependency_overrides[get_db] = dependency
        messages = []
        with patch.object(settings, "PASSWORD_RECOVERY_ENABLED", True), \
                patch("app.services.password_recovery.SessionLocal", factory), \
                patch("app.services.request_limits.SessionLocal", factory), \
                patch("app.services.password_recovery.send_otp_message", side_effect=lambda *args: messages.append(args)):
            def post(path, payload):
                with TestClient(app, headers={"X-CRM-Request": "1"}) as client:
                    return client.post(path, json=payload)

            requested = post("/api/auth/forgot-password", {"email": "race@example.test"})
            assert requested.status_code == 202
            challenge, code = requested.json()["challengeId"], messages[-1][1]
            wrong = "000000" if code != "000000" else "000001"
            # Concurrent failed attempts must persist, without lost increments.
            with ThreadPoolExecutor(max_workers=4) as pool:
                attempts = list(pool.map(lambda _: post("/api/auth/verify-reset-otp", {"challengeId": challenge, "code": wrong}), range(4)))
            assert all(result.status_code == 400 for result in attempts)
            from app.models.password_reset import PasswordResetToken
            with factory() as db:
                assert db.scalar(select(PasswordResetToken.failed_attempts)) == 4
            # Exactly one concurrent correct verification may receive a reset grant.
            with ThreadPoolExecutor(max_workers=2) as pool:
                verified = list(pool.map(lambda _: post("/api/auth/verify-reset-otp", {"challengeId": challenge, "code": code}), range(2)))
            assert sorted(result.status_code for result in verified) == [200, 400]
            grant = next(result.json()["resetToken"] for result in verified if result.status_code == 200)
            # Exactly one reset may consume the verified grant.
            with ThreadPoolExecutor(max_workers=2) as pool:
                resets = list(pool.map(lambda _: post("/api/auth/reset-password", {"token": grant, "newPassword": "QaNew123"}), range(2)))
            assert sorted(result.status_code for result in resets) == [204, 400]
            with factory() as db:
                user = db.get(User, user_id)
                assert passwords.verify("QaNew123", user.password_hash)
                assert user.version == 2 and user.role == "Staff"
    finally:
        app.dependency_overrides.clear()
        qa.dispose()
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
    print("PostgreSQL concurrent OTP attempts, verification and password reset passed; QA schema removed.", flush=True)


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10, "options": "-c statement_timeout=15000"}, hide_parameters=True)
    assert engine.dialect.name == "postgresql"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision in {"20261104_0006", "20261105_0007", "20261105_0008", "20261105_0009", "20261105_0010", "20261105_0011", "20261106_0012", "20261106_0013", "20261106_0014", "20261106_0015", "20261110_0016", "20261110_0017"}, "Unexpected migration revision"
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
            with patch.object(settings, "PASSWORD_RECOVERY_ENABLED", True), patch("app.services.password_recovery.SessionLocal", factory), patch("app.services.request_limits.SessionLocal", factory), patch("app.services.password_recovery.send_otp_message", side_effect=lambda *args: messages.append(args)), TestClient(app, headers={"X-CRM-Request": "1"}) as client:
                login = client.post("/api/auth/login", json={"email": "qa@example.test", "password": "QaOld123"})
                assert login.status_code == 200
                requested = client.post("/api/auth/forgot-password", json={"email": "qa@example.test"})
                assert requested.status_code == 202
                challenge = requested.json()["challengeId"]
                assert client.post("/api/auth/reset-password", json={"token": challenge, "newPassword": "QaNew123"}).status_code == 400
                verified = client.post("/api/auth/verify-reset-otp", json={"challengeId": challenge, "code": messages[0][1]})
                assert verified.status_code == 200
                assert client.post("/api/auth/verify-reset-otp", json={"challengeId": challenge, "code": messages[0][1]}).status_code == 400
                token = verified.json()["resetToken"]
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
    verify_concurrent_otp(engine)
    engine.dispose()
    print("PostgreSQL recovery, replay prevention and session revocation passed; QA schema rolled back; mail mocked; no real email sent.")


if __name__ == "__main__":
    main()
