"""Migrate with preservation assertions, then test PostgreSQL in a disposable schema."""
from pathlib import Path
import re
import sys
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.lead import Lead
from app.models.customer import Customer
from app.models.follow_up import FollowUp
from app.models.user import User


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) in {"20261105_0010", "20261105_0011", "20261106_0012", "20261106_0013", "20261106_0014", "20261106_0015", "20261110_0016", "20261110_0017"}
        users = connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        snapshots = {name: connection.execute(text(f"SELECT to_jsonb(t) - 'version' - 'customer_id' FROM {name} t ORDER BY id")).all() for name in ["leads", "customers", "quotations"]}
        files = connection.execute(text("SELECT id, sha256, md5(content), snapshot FROM quotation_files ORDER BY id")).all()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert not compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
        assert users == connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        for name, original in snapshots.items():
            assert original == connection.execute(text(f"SELECT to_jsonb(t) - 'version' - 'customer_id' FROM {name} t ORDER BY id")).all()
        assert files == connection.execute(text("SELECT id, sha256, md5(content), snapshot FROM quotation_files ORDER BY id")).all()
        links = {name: connection.scalar(text(f"SELECT count(*) FROM {name} WHERE customer_id IS NOT NULL")) for name in ["leads", "quotations"]}
    print("Migration 0011 applied. Accounts, assignments, names, documents and PDF bytes preserved. Linked counts:", links)
    schema = "qa_customer_links_" + uuid4().hex
    assert re.fullmatch(r"qa_customer_links_[a-f0-9]{32}", schema)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA " + schema)
    qa = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5, "options": "-csearch_path=" + schema})
    try:
        Base.metadata.create_all(qa, checkfirst=False)
        factory = sessionmaker(bind=qa)
        with factory() as db:
            owner = User(name="QA Owner", email="qa-links@example.test", role="Admin", is_owner=True, admin_slot=1, password_hash=passwords.hash("QaLinks123"))
            db.add(owner); db.flush()
            customer = Customer(name="QA Profile", assignee_user_id=owner.id)
            db.add(customer); db.flush()
            profile_id = customer.id
            for index in range(125):
                lead = Lead(customer="QA Profile", customer_id=customer.id, division="MMC", description="QA", priority="High", assignee_user_id=owner.id)
                db.add(lead); db.flush()
                db.add(FollowUp(lead_id=lead.id, purpose="QA Task", due_at=datetime.now(timezone.utc) + timedelta(minutes=10), reminder_minutes=30))
            db.commit()
        def qa_db():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = qa_db
        with patch("app.services.request_limits.SessionLocal", factory), TestClient(app, headers={"X-CRM-Request": "1"}) as client:
            login = client.post("/api/auth/login", json={"email": "qa-links@example.test", "password": "QaLinks123"})
            assert login.status_code == 200
            client.headers.update({"Authorization": "Bearer " + login.json()["accessToken"]})
            overview = client.get("/api/workspace/overview")
            assert overview.status_code == 200, overview.text
            data = overview.json()
            assert data["metrics"]["leads"]["total"] == 125
            assert len(data["alertFollowUps"]) == 20 and len(data["recentLeads"]) == 5
            page = client.get("/api/leads", params={"customerId": profile_id, "paged": True, "pageSize": 25}).json()
            assert page["total"] == 125 and len(page["items"]) == 25
            quote = client.post("/api/quotations", json={"customer": "QA Profile", "customerId": profile_id, "division": "MMC", "date": "2026-11-06", "items": [{"description": "QA", "quantity": 1, "rate": 100}]} )
            assert quote.status_code == 201, quote.text
            compact = client.get("/api/quotations?paged=true&summary=true").json()["items"][0]
            assert compact["customerId"] == profile_id and "snapshot" not in compact["versions"][0]
        print("PostgreSQL verified: exact totals across 125 rows, bounded previews/reminders, paged ID filtering, linked quotation + compact PDF metadata.")
    finally:
        app.dependency_overrides.clear()
        qa.dispose()
        assert re.fullmatch(r"qa_customer_links_[a-f0-9]{32}", schema)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
        engine.dispose()
    print("Disposable QA schema removed; real CRM data was not seeded or edited.")


if __name__ == "__main__":
    try:
        main()
    except OperationalError:
        print("Configured database is unreachable. Verify connectivity and migration status from the database host; credentials were not displayed.")
        raise SystemExit(2) from None
