"""Read-only CRM timings and rate-budget tests in one disposable PostgreSQL schema."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.models.user import User
from app.models.rate_limit import RateLimitBucket
from app.services.request_limits import enforce_limits, postgres_limits
from app.services.settings import settings_response
from app.routers.workspace import metrics, overview


def main():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10, "options": "-c statement_timeout=15000"}, hide_parameters=True)
    assert engine.dialect.name == "postgresql"
    statements = [0]
    @event.listens_for(engine, "before_cursor_execute")
    def count(*args):
        statements[0] += 1
    results = {}
    schema = "qa_latency_" + uuid4().hex
    assert re.fullmatch(r"qa_latency_[a-f0-9]{32}", schema)
    created = False
    qa = None
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            with Session(bind=connection) as db:
                user = db.scalar(select(User).where(User.is_active.is_(True)).order_by(User.is_owner.desc()).limit(1))
                assert user is not None, "An existing active account is needed to measure scoped reads"
                db.info["crm_actor"] = user
                for name, operation in [("settings", lambda: settings_response(db, user)), ("metrics", lambda: metrics(db)), ("overview", lambda: overview(division=None, db=db))]:
                    statements[0] = 0
                    started = time.perf_counter()
                    operation()
                    results[name] = {"seconds": round(time.perf_counter() - started, 3), "sqlStatements": statements[0]}
            connection.rollback()
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE SCHEMA " + schema)
        created = True
        qa = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 10, "options": "-csearch_path=" + schema}, pool_size=4, max_overflow=0, hide_parameters=True)
        with qa.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
        RateLimitBucket.__table__.create(qa, checkfirst=False)
        factory = sessionmaker(bind=qa)
        at = datetime.now(timezone.utc)
        budgets = [("a" * 64, 3, 60), ("b" * 64, 1, 10)]
        with factory() as db:
            assert postgres_limits(db, budgets, at) == 0
            assert postgres_limits(db, budgets, at) == 10
            assert postgres_limits(db, budgets, at) == 10
            assert postgres_limits(db, budgets, at) == 60
            assert dict(db.execute(select(RateLimitBucket.key, RateLimitBucket.count)).all()) == {"a" * 64: 3, "b" * 64: 1}
            assert postgres_limits(db, budgets, at + timedelta(seconds=11)) == 49
            assert postgres_limits(db, budgets, at + timedelta(seconds=61)) == 0
            db.commit()
        identity = uuid4().hex
        def attempt(_):
            try:
                enforce_limits([("qa-latency", identity, 5, 60)])
                return 200
            except HTTPException as error:
                return error.status_code
        with patch("app.services.request_limits.SessionLocal", factory), ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(attempt, range(12)))
        results["rateLimitConcurrency"] = {"allowed": statuses.count(200), "limited": statuses.count(429), "storageErrors": statuses.count(503)}
        assert statuses.count(200) == 5 and statuses.count(429) == 7, "Concurrent quota mismatch"
        results["rateLimitWindowsAndDeniedCounts"] = "passed"
    finally:
        if qa is not None:
            qa.dispose()
        if created:
            assert re.fullmatch(r"qa_latency_[a-f0-9]{32}", schema)
            with engine.begin() as connection:
                connection.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}) == 0
        engine.dispose()
    results["cleanup"] = "QA schema removed; existing CRM records and login accounts were not edited"
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"verification": "failed", "errorType": type(error).__name__, "detail": "Credentials and database contents omitted"}))
        raise SystemExit(1) from None
