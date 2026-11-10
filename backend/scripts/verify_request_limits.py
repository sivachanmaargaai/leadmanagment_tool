"""Additive migration + PostgreSQL API protection/concurrency checks; no live account changes."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.rate_limit import RateLimitBucket
from app.models.user import User
from app.services.request_limits import enforce_limits


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        old = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert old in {"20261105_0008", "20261105_0009", "20261105_0010", "20261105_0011", "20261106_0012", "20261106_0013", "20261106_0014", "20261106_0015", "20261110_0016", "20261110_0017"}, "Unexpected migration revision"
        existing = set(inspect(connection).get_table_names()) & set(Base.metadata.tables)
        counts = {name: connection.scalar(text(f'SELECT COUNT(*) FROM "{name}"')) for name in existing}
        users = connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        assignments = {name: connection.execute(text(f'SELECT id, assignee_user_id FROM "{name}" ORDER BY id')).all() for name in ("leads", "customers", "quotations")}
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert not compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
        assert counts == {name: connection.scalar(text(f'SELECT COUNT(*) FROM "{name}"')) for name in existing}
        assert users == connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        assert assignments == {name: connection.execute(text(f'SELECT id, assignee_user_id FROM "{name}" ORDER BY id')).all() for name in assignments}
    print("Migration 0009 matches models; existing record counts, login rows and CRM assignments preserved.")

    schema = "qa_limits_" + uuid4().hex
    # Use a committed, isolated QA schema so budgets and handler transactions use
    # independent physical connections. A shared outer test transaction would
    # incorrectly roll a committed rate budget back with the business request.
    import re
    assert re.fullmatch(r"qa_limits_[a-f0-9]{32}", schema)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA " + schema)
    qa_engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5, "options": "-csearch_path=" + schema})
    try:
        with qa_engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
        Base.metadata.create_all(qa_engine, checkfirst=False)
        factory = sessionmaker(bind=qa_engine)
        with factory() as db:
            db.add(User(email="qa@example.test", name="QA Owner", role="Admin", is_owner=True, admin_slot=1, password_hash=passwords.hash("QaLimit123")))
            db.commit()
        def qa_db():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = qa_db
        with patch("app.services.request_limits.SessionLocal", factory), TestClient(app, headers={"X-CRM-Request": "1"}) as client:
            login = client.post("/api/auth/login", json={"email": "qa@example.test", "password": "QaLimit123"})
            assert login.status_code == 200
            client.headers["Authorization"] = "Bearer " + login.json()["accessToken"]
            with patch.object(settings, "LOGIN_EMAIL_PER_15_MINUTES", 3):
                for _ in range(2):
                    assert client.post("/api/auth/login", json={"email": "qa@example.test", "password": "wrong"}).status_code == 401
                blocked_login = client.post("/api/auth/login", json={"email": " QA@EXAMPLE.TEST ", "password": "QaLimit123"})
                assert blocked_login.status_code == 429, f"Expected login limit, got {blocked_login.status_code}"
            assert client.get("/api/auth/me").status_code == 200
            with patch.object(settings, "REQUEST_JSON_MAX_BYTES", 1024):
                result = client.post("/api/leads", json={"customer": "Large", "division": "MMC", "description": "x" * 2048})
                assert result.status_code == 413
                with factory() as db:
                    assert db.scalar(text("SELECT count(*) FROM leads")) == 0
            with factory() as db:
                db.execute(delete(RateLimitBucket))  # This engine sees only the isolated QA schema.
                db.commit()
            with patch.object(settings, "API_IP_PER_MINUTE", 2):
                assert client.get("/api/auth/me").status_code == 200
                assert client.get("/api/missing").status_code == 404
                blocked = client.get("/api/leads", headers={"X-Forwarded-For": "203.0.113.99", "Origin": "http://localhost:5173"})
                assert blocked.status_code == 429
                assert int(blocked.headers["retry-after"]) > 0
                assert blocked.headers["access-control-allow-origin"] == "http://localhost:5173"
                assert client.get("/api/health").status_code == 200
        print("PostgreSQL login/API limits, oversized-write rejection, CORS and session preservation passed.")
        identity = "qa-" + uuid4().hex
        def attempt(_):
            try:
                enforce_limits([("qa-concurrency", identity, 5, 60)])
                return 200
            except HTTPException as error:
                return error.status_code
        with patch("app.services.request_limits.SessionLocal", factory), ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(attempt, range(20)))
        assert statuses.count(200) == 5 and statuses.count(429) == 15, "Concurrent quota mismatch"
        print("20 concurrent PostgreSQL attempts across independent connections: exactly 5 allowed, 15 limited.")
    finally:
        app.dependency_overrides.clear()
        qa_engine.dispose()
        # Only the exact internally generated schema created above is removed.
        assert re.fullmatch(r"qa_limits_[a-f0-9]{32}", schema)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}) == 0
    engine.dispose()
    print("Isolated QA schema/accounts/budgets removed; live login accounts were not modified.")


if __name__ == "__main__":
    main()
