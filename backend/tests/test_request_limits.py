import asyncio
import os
import tempfile
import unittest
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.config import Settings, settings
from app.core.request_guard import RequestGuardMiddleware
from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.rate_limit import RateLimitBucket
from app.models.user import User
from app.services.request_limits import enforce_limits, now
from auth_helpers import TEST_PASSWORD, isolate_request_limits, test_password_hash


class RequestLimitTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'limits.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="owner@example.test", name="Owner", role="Admin", password_hash=test_password_hash())
        self.db.add(self.user)
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app, headers={"X-CRM-Request": "1"})

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def login(self, email="owner@example.test", password=TEST_PASSWORD):
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def test_ip_limits_count_unauthorized_unknown_and_malformed_requests(self):
        with patch.object(settings, "API_IP_PER_MINUTE", 2):
            self.assertEqual(self.client.get("/api/missing").status_code, 404)
            self.assertEqual(self.client.post("/api/auth/login", content=b"{invalid", headers={"Content-Type": "application/json"}).status_code, 422)
            limited = self.client.get("/api/leads", headers={"Origin": "http://localhost:5173", "X-Forwarded-For": "203.0.113.99"})
            self.assertEqual(limited.status_code, 429)
            self.assertGreater(int(limited.headers["retry-after"]), 0)
            self.assertEqual(limited.headers["cache-control"], "no-store")
            self.assertEqual(limited.headers["access-control-allow-origin"], "http://localhost:5173")
            self.assertIn("Retry-After", limited.headers["access-control-expose-headers"])
            self.assertEqual(self.client.get("/api/health").status_code, 200)
            self.assertEqual(self.client.options("/api/leads", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"}).status_code, 200)

    def test_burst_and_window_expiry(self):
        at = now()
        with patch.object(settings, "API_IP_BURST_PER_10_SECONDS", 1), patch("app.services.request_limits.now", return_value=at):
            self.assertEqual(self.client.get("/api/leads").status_code, 401)
            self.assertEqual(self.client.get("/api/leads").status_code, 429)
        with patch.object(settings, "API_IP_BURST_PER_10_SECONDS", 1), patch("app.services.request_limits.now", return_value=at + timedelta(seconds=11)):
            self.assertEqual(self.client.get("/api/leads").status_code, 401)

    def test_login_email_limits_normalize_and_stop_password_hash_work(self):
        with patch.object(settings, "LOGIN_EMAIL_PER_15_MINUTES", 2), patch.object(passwords, "verify_and_update", wraps=passwords.verify_and_update) as verify:
            self.assertEqual(self.login(password="wrong").status_code, 401)
            self.assertEqual(self.login(email=" OWNER@EXAMPLE.TEST ", password="wrong").status_code, 401)
            limited = self.login()
            self.assertEqual(limited.status_code, 429)
            self.assertEqual(verify.call_count, 2)
            self.assertNotIn("accessToken", limited.json())
            self.assertNotIn("set-cookie", limited.headers)
        self.db.expire_all()
        for bucket in self.db.scalars(select(RateLimitBucket)).all():
            self.assertEqual(len(bucket.key), 64)
            self.assertNotIn("owner", bucket.key)

    def test_login_ip_limits_span_accounts_and_unknown_email_matches_known(self):
        with patch.object(settings, "LOGIN_IP_PER_15_MINUTES", 2):
            self.assertEqual(self.login(email="missing1@example.test").status_code, 401)
            self.assertEqual(self.login(email="missing2@example.test").status_code, 401)
            self.assertEqual(self.login().status_code, 429)

    def test_authenticated_user_and_write_budgets_preserve_failed_write_counts(self):
        data = self.login().json()
        headers = {"Authorization": "Bearer " + data["accessToken"]}
        with patch.object(settings, "API_USER_WRITES_PER_MINUTE", 1):
            self.assertEqual(self.client.post("/api/leads", headers=headers, json={"customer": "Bad", "division": "invalid"}).status_code, 422)
            self.assertEqual(self.client.post("/api/leads", headers=headers, json={"customer": "Valid", "division": "MMC"}).status_code, 429)
            self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        with patch.object(settings, "API_USER_PER_MINUTE", 1):
            self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 429)

    def test_storage_failure_is_safe_503_while_health_remains_available(self):
        with patch("app.services.request_limits.SessionLocal", side_effect=SQLAlchemyError("sensitive connection detail")), self.assertLogs("app.services.request_limits", level="WARNING") as logs:
            result = self.client.get("/api/leads")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.headers["retry-after"], "5")
        self.assertNotIn("sensitive connection detail", " ".join(logs.output) + result.text)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_distinct_sessions_share_atomic_budget_under_concurrent_attempts(self):
        def attempt(_):
            try:
                enforce_limits([("concurrent", "same-client", 5, 60)])
                return 200
            except HTTPException as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(attempt, range(15)))
        self.assertEqual(statuses.count(200), 5)
        self.assertEqual(statuses.count(429), 10)

    def test_production_cannot_disable_limits_and_body_config_is_bounded(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, DATABASE_URL="sqlite://", ENVIRONMENT="production", COOKIE_SECURE=True, ALLOWED_ORIGINS=["https://crm.example.test"], RATE_LIMIT_ENABLED=False)
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, DATABASE_URL="sqlite://", REQUEST_JSON_MAX_BYTES=0)


class BodyGuardTests(unittest.TestCase):
    def run_guard(self, chunks, headers=None, path="/api/leads", delay=0):
        received, sent = [], []
        async def endpoint(scope, receive, send):
            received.append(await receive())
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})
        messages = deque({"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1} for i, chunk in enumerate(chunks))
        async def receive():
            if delay:
                await asyncio.sleep(delay)
            return messages.popleft() if messages else {"type": "http.disconnect"}
        async def send(message):
            sent.append(message)
        scope = {"type": "http", "method": "POST", "path": path, "raw_path": path.encode(), "headers": headers or [], "query_string": b"", "client": ("127.0.0.1", 123)}
        with patch("app.core.request_guard.enforce_ip_limits"):
            asyncio.run(RequestGuardMiddleware(endpoint)(scope, receive, send))
        return sent[0]["status"] if sent else None, received

    def test_chunked_body_and_lying_lengths_never_reach_handler_when_oversized(self):
        with patch.object(settings, "REQUEST_JSON_MAX_BYTES", 5):
            self.assertEqual(self.run_guard([b"abc", b"def"]), (413, []))
            self.assertEqual(self.run_guard([b"abc", b"def"], [(b"content-length", b"2")]), (413, []))
            status, received = self.run_guard([b"ab", b"cde"])
            self.assertEqual(status, 200)
            self.assertEqual(received[0]["body"], b"abcde")

    def test_auth_upload_and_json_caps_are_separate(self):
        with patch.object(settings, "REQUEST_JSON_MAX_BYTES", 5), patch.object(settings, "REQUEST_AUTH_MAX_BYTES", 3), patch.object(settings, "REQUEST_UPLOAD_MAX_BYTES", 10):
            self.assertEqual(self.run_guard([b"1234"], path="/api/auth/login"), (413, []))
            multipart = [(b"content-type", b"multipart/form-data; boundary=test")]
            self.assertEqual(self.run_guard([b"123456"], multipart, "/api/quotations/upload")[0], 200)
            self.assertEqual(self.run_guard([b"123456"], multipart, "/api/leads"), (413, []))
            self.assertEqual(self.run_guard([b"12345678901"], multipart, "/api/quotations/x/revisions"), (413, []))

    def test_headers_urls_encoding_framing_and_read_timeout(self):
        self.assertEqual(self.run_guard([b""], [(b"content-length", b"4"), (b"content-length", b"4")]), (400, []))
        self.assertEqual(self.run_guard([b""], [(b"content-length", b"0"), (b"transfer-encoding", b"chunked")]), (400, []))
        self.assertEqual(self.run_guard([b""], [(b"content-length", b"-1")]), (400, []))
        self.assertEqual(self.run_guard([b"a"], [(b"content-length", b"2")]), (400, []))
        self.assertEqual(self.run_guard([b""], [(b"content-encoding", b"gzip")]), (415, []))
        with patch.object(settings, "REQUEST_HEADER_MAX_BYTES", 10):
            self.assertEqual(self.run_guard([b""], [(b"x-big", b"x" * 20)]), (431, []))
        with patch.object(settings, "REQUEST_URL_MAX_BYTES", 4):
            self.assertEqual(self.run_guard([b""]), (414, []))
        with patch.object(settings, "REQUEST_BODY_TIMEOUT_SECONDS", 0.01):
            self.assertEqual(self.run_guard([b""], delay=0.1), (408, []))
