"""Migrate common Staff permissions and verify isolated PostgreSQL APIs."""
from pathlib import Path
import json
import re
import secrets
import sys
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Boolean, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10, "options": "-c statement_timeout=15000"}, hide_parameters=True)
    assert engine.dialect.name == "postgresql"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        previous = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert previous in {"20261106_0012", "20261106_0013", "20261106_0014", "20261106_0015", "20261110_0016", "20261110_0017"}, "Unexpected migration revision"
        users = connection.execute(text("SELECT * FROM users ORDER BY id")).all()
        sessions = connection.execute(text("SELECT * FROM auth_sessions ORDER BY id")).mappings().all()
        staff_ids = set(connection.execute(text("SELECT id FROM users WHERE role='Staff'")).scalars())
        counts = {name: connection.scalar(text(f"SELECT count(*) FROM {name}")) for name in ["leads", "customers", "follow_ups", "quotations", "quotation_files"]}
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert users == connection.execute(text("SELECT * FROM users ORDER BY id")).all()
        after_sessions = {row["id"]: row for row in connection.execute(text("SELECT * FROM auth_sessions ORDER BY id")).mappings()}
        for original in sessions:
            after = after_sessions[original["id"]]
            assert {k: v for k, v in original.items() if k != "revoked_at"} == {k: v for k, v in after.items() if k != "revoked_at"}
            if previous == "20261106_0012" and original["user_id"] in staff_ids and original["revoked_at"] is None:
                assert after["revoked_at"] is not None
            else:
                assert original["revoked_at"] == after["revoked_at"]
        assert counts == {name: connection.scalar(text(f"SELECT count(*) FROM {name}")) for name in counts}
        assert inspect(connection).has_table("role_permissions")
        if previous == "20261106_0012":
            assert connection.scalar(text("SELECT quotations FROM role_permissions WHERE role='Staff'")) is False
    print("Migration 0013 verified: common Staff policy starts OFF; user/password fields and CRM counts preserved. Admin sessions retained; Staff sessions refreshed.", flush=True)
    schema = "qa_quote_permissions_" + uuid4().hex
    assert re.fullmatch(r"qa_quote_permissions_[a-f0-9]{32}", schema)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA " + schema)
    qa = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10, "options": "-csearch_path=" + schema}, hide_parameters=True)
    results = []
    try:
        Base.metadata.create_all(qa, checkfirst=False)
        factory = sessionmaker(bind=qa)
        password = secrets.token_urlsafe(18)
        with factory() as db:
            owner = User(name="QA Owner", email="owner@example.test", role="Admin", is_owner=True, admin_slot=1, password_hash=passwords.hash(password))
            admin = User(name="QA Admin", email="admin@example.test", role="Admin", admin_slot=2, password_hash=passwords.hash(password))
            staff = User(name="QA Staff", email="staff@example.test", role="Staff", password_hash=passwords.hash(password))
            other = User(name="QA Other", email="other@example.test", role="Staff", quotation_access=True, password_hash=passwords.hash(password))
            db.add_all([owner, admin, staff, other]); db.commit()
            owner_id, staff_id = owner.id, staff.id
        def qa_db():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = qa_db
        with patch("app.services.request_limits.SessionLocal", factory), TestClient(app, headers={"X-CRM-Request": "1"}) as client:
            def login(email):
                response = client.post("/api/auth/login", json={"email": email, "password": password})
                assert response.status_code == 200
                return {"Authorization": "Bearer " + response.json()["accessToken"]}, response.json()["user"]
            owner_headers, _ = login("owner@example.test")
            admin_headers, _ = login("admin@example.test")
            staff_headers, profile = login("staff@example.test")
            assert profile["canAccessQuotations"] is False
            assert client.get("/api/quotations", headers=staff_headers).status_code == 403
            response = client.post("/api/quotations", headers=owner_headers, json={"number": "QA-PERM-001", "customer": "QA Customer", "division": "MMC", "date": "2026-11-06", "items": [{"description": "QA Firmware", "quantity": 1, "rate": 100}]})
            assert response.status_code == 201
            quote = response.json()
            assigned = client.put(f"/api/access/assignments/quotations/{quote['id']}", headers=owner_headers, json={"assigneeUserId": staff_id, "expectedAssigneeUserId": owner_id, "expectedVersion": quote["version"]})
            assert assigned.status_code == 200
            pdf = quote["versions"][0]["pdfPath"]
            assert client.get(pdf, headers=staff_headers).status_code == 403
            other_headers, other_profile = login("other@example.test")
            assert other_profile["canAccessQuotations"] is False  # Legacy per-user flag is ignored.
            policy = client.get("/api/permissions", headers=admin_headers).json()
            assert policy["roles"]["Admin"]["readOnly"] and policy["roles"]["Admin"]["quotations"]
            granted = client.put("/api/permissions/staff", headers=admin_headers, json={"quotations": True, "expectedVersion": policy["version"]})
            assert granted.status_code == 200 and granted.json()["roles"]["Staff"]["quotations"]
            assert client.get("/api/auth/me", headers=staff_headers).status_code == 401
            assert client.get("/api/auth/me", headers=other_headers).status_code == 401
            staff_headers, staff_profile = login("staff@example.test")
            other_headers, other_profile = login("other@example.test")
            assert staff_profile["canAccessQuotations"] and other_profile["canAccessQuotations"]
            assert client.get(pdf, headers=staff_headers).status_code == 200
            assert client.get(pdf, headers=other_headers).status_code == 404
            stale = client.put("/api/permissions/staff", headers=owner_headers, json={"quotations": False, "expectedVersion": policy["version"]})
            assert stale.status_code == 409
            revoked = client.put("/api/permissions/staff", headers=owner_headers, json={"quotations": False, "expectedVersion": granted.json()["version"]})
            assert revoked.status_code == 200
            assert client.get(pdf, headers=staff_headers).status_code == 401
            assert client.get("/api/auth/me", headers=other_headers).status_code == 401
            staff_headers, _ = login("staff@example.test")
            assert client.get(pdf, headers=staff_headers).status_code == 403
            assert client.get("/api/reports/sales", headers=staff_headers).status_code == 403
            summary = client.get("/api/reports/summary", headers=staff_headers).json()
            assert "acceptedValue" not in summary and "totalQuotations" not in summary["totals"]
            assert "quotation" not in client.get("/api/settings", headers=staff_headers).json()
            assert client.put("/api/permissions/staff", headers=staff_headers, json={"quotations": True, "expectedVersion": revoked.json()["version"]}).status_code == 403
            assert client.put(f"/api/users/{staff_id}/quotation-access", headers=owner_headers, json={"enabled": True, "expectedVersion": 1}).status_code == 410
            assert client.get("/api/auth/me", headers=admin_headers).status_code == 200
            results = ["common Staff default-deny", "legacy grants ignored", "both Admins manage role", "all Staff updated together", "real PDF access", "assignment scope", "version conflict", "Staff-only session revocation", "sales/settings/summary redaction", "no self-grant", "retired individual API"]
    finally:
        app.dependency_overrides.clear()
        qa.dispose()
        assert re.fullmatch(r"qa_quote_permissions_[a-f0-9]{32}", schema)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}) == 0
        engine.dispose()
    print(json.dumps({"postgresqlApiChecks": results, "cleanup": "QA schema/accounts/PDFs removed; the real common Staff permission was not changed by QA"}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"verification": "failed", "errorType": type(error).__name__, "detail": "Credentials and database contents omitted"}))
        raise SystemExit(1) from None
