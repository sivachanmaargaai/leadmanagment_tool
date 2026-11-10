"""Preserve live data, migrate, then race edits in an isolated PostgreSQL QA schema."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.lead import Lead
from app.models.user import User


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision in {"20261105_0009", "20261105_0010", "20261105_0011", "20261106_0012", "20261106_0013", "20261106_0014", "20261106_0015", "20261110_0016", "20261110_0017"}, "Unexpected migration head"
        tables = set(inspect(connection).get_table_names()) & set(Base.metadata.tables)
        counts = {name: connection.scalar(text(f'SELECT count(*) FROM "{name}"')) for name in tables}
        users = connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        snapshots = {name: connection.execute(text(f'SELECT to_jsonb(t) - \'version\' - \'customer_id\' FROM "{name}" t ORDER BY id')).all() for name in ("leads", "customers")}
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert not compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
        assert counts == {name: connection.scalar(text(f'SELECT count(*) FROM "{name}"')) for name in tables}
        assert users == connection.execute(text("SELECT to_jsonb(t) - 'quotation_access' FROM users t ORDER BY id")).all()
        assert snapshots == {name: connection.execute(text(f'SELECT to_jsonb(t) - \'version\' - \'customer_id\' FROM "{name}" t ORDER BY id')).all() for name in snapshots}
    print("Current migration head matches models; existing record counts, lead/customer fields and login accounts preserved.")

    schema = "qa_pages_" + uuid4().hex
    assert re.fullmatch(r"qa_pages_[a-f0-9]{32}", schema)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA " + schema)
    qa_engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5, "options": "-csearch_path=" + schema})
    try:
        with qa_engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
        Base.metadata.create_all(qa_engine, checkfirst=False)
        factory = sessionmaker(bind=qa_engine)
        with factory() as db:
            user = User(email="qa@example.test", name="QA Owner", role="Admin", is_owner=True, admin_slot=1, password_hash=passwords.hash("QaPages123"))
            db.add(user)
            db.commit()
            user_id = user.id
        def qa_db():
            with factory() as db:
                yield db
        app.dependency_overrides[get_db] = qa_db
        with patch("app.services.request_limits.SessionLocal", factory), TestClient(app, headers={"X-CRM-Request": "1"}) as client:
            login = client.post("/api/auth/login", json={"email": "qa@example.test", "password": "QaPages123"})
            assert login.status_code == 200
            headers = {"Authorization": "Bearer " + login.json()["accessToken"], "X-CRM-Request": "1"}
            client.headers.update(headers)
            with factory() as db:
                at = datetime.now(timezone.utc)
                db.add_all([Lead(customer=f"Page {i:03}", division="MMC", description="Embedded", created_at=at, assignee_user_id=user_id) for i in range(125)])
                db.commit()
            batches = [client.get(f"/api/leads?paged=true&page={page}&pageSize=50&q=Page").json() for page in (1, 2, 3)]
            assert [len(batch["items"]) for batch in batches] == [50, 50, 25]
            assert all(batch["total"] == 125 for batch in batches)
            assert len({item["id"] for batch in batches for item in batch["items"]}) == 125
            assert len(client.get("/api/leads").json()) == 100
            lead = client.post("/api/leads", json={"customer": "Race lead", "division": "MMC", "description": "Initial"}).json()
            customer = client.post("/api/customers", json={"name": "Race customer", "divisions": ["MMC"], "contacts": [{"phone": "1234567890"}]}).json()
            task = client.post("/api/follow-ups", json={"leadId": lead["id"], "purpose": "Race completion", "dueAt": (at + timedelta(days=1)).isoformat()}).json()
            def race(path, payloads):
                barrier = Barrier(2)
                def request(payload):
                    with TestClient(app, headers=headers) as worker:
                        barrier.wait(timeout=10)
                        result = worker.put(path, json=payload)
                        return result.status_code, payload
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(request, payloads))
                assert sorted(status for status, _ in outcomes) == [200, 409], "Concurrent edit did not produce one winner"
                return next(payload for status, payload in outcomes if status == 200)
            winner = race("/api/leads/" + lead["id"], [{"expectedVersion": 1, "description": "Editor A"}, {"expectedVersion": 1, "description": "Editor B"}])
            latest = client.get("/api/leads/" + lead["id"]).json()
            assert latest["version"] == 2 and latest["description"] == winner["description"]
            assert client.delete(f"/api/leads/{lead['id']}?expectedVersion=1").status_code == 409
            winner = race("/api/customers/" + customer["id"], [{"expectedVersion": 1, "notes": "Editor A", "contacts": [{"phone": "111"}]}, {"expectedVersion": 1, "notes": "Editor B", "contacts": [{"phone": "222"}]}])
            latest = client.get("/api/customers/" + customer["id"]).json()
            assert latest["version"] == 2 and latest["notes"] == winner["notes"] and latest["contacts"][0]["phone"] == winner["contacts"][0]["phone"]
            completion = {"expectedVersion": 1, "status": "Completed", "outcome": "Connected", "completionNotes": "Discussed", "nextDueAt": (at + timedelta(days=2)).isoformat()}
            race("/api/follow-ups/" + task["id"], [completion, completion])
            assert client.get("/api/follow-ups?paged=true").json()["total"] == 2
            print("PostgreSQL pages: 50/50/25 unique records; concurrent lead/customer edits and follow-up completion: one 200 + one 409 each.")
    finally:
        app.dependency_overrides.clear()
        qa_engine.dispose()
        assert re.fullmatch(r"qa_pages_[a-f0-9]{32}", schema)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}) == 0
    engine.dispose()
    print("QA schema/accounts/data removed; no real account or CRM record was edited.")


if __name__ == "__main__":
    main()
