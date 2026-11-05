import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import Settings, settings
from app.core.security import now, token_hash
from app.db.database import Base, get_db
from app.main import app
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from auth_helpers import isolate_request_limits, TEST_PASSWORD, test_password_hash


class PasswordRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'reset.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="owner@example.test", name="Owner", role="Admin", is_owner=True, admin_slot=1, password_hash=test_password_hash())
        self.db.add(self.user)
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app, headers={"X-CRM-Request": "1"})
        self.mail = []
        self.patches = [patch.object(settings, "PASSWORD_RECOVERY_ENABLED", True),
                        patch("app.services.password_recovery.SessionLocal", sessionmaker(bind=self.engine)),
                        patch("app.services.password_recovery.send_reset_message", side_effect=lambda *args: self.mail.append(args))]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def request_link(self, email="owner@example.test", **kwargs):
        return self.client.post("/api/auth/forgot-password", json={"email": email}, **kwargs)

    def token(self):
        return parse_qs(urlsplit(self.mail[-1][1]).fragment.split("?", 1)[1])["token"][0]

    def reset(self, token=None, password="New8char"):
        return self.client.post("/api/auth/reset-password", json={"token": token or self.token(), "newPassword": password})

    def test_generic_response_and_hashed_token_with_trusted_link(self):
        known = self.request_link(headers={"Host": "attacker.test"})
        missing = self.request_link("missing@example.test")
        self.assertEqual(known.status_code, 202)
        self.assertEqual(known.json(), missing.json())
        self.assertEqual(known.headers["cache-control"], "no-store")
        self.assertEqual(len(self.mail), 1)
        self.assertEqual(self.mail[0][0], self.user.email)
        self.assertTrue(self.mail[0][1].startswith(settings.RESET_BASE_URL + "/#reset-password?"))
        self.db.expire_all()
        stored = self.db.scalar(select(PasswordResetToken))
        self.assertEqual(stored.token_hash, token_hash(self.token()))
        self.assertEqual(stored.delivery_status, "sent")
        self.assertNotIn(self.token(), known.text)

    def test_reset_revokes_sessions_preserves_owner_and_rejects_replay(self):
        login = self.client.post("/api/auth/login", json={"email": self.user.email, "password": TEST_PASSWORD}).json()
        headers = {"Authorization": "Bearer " + login["accessToken"]}
        self.request_link()
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        token = self.token()
        self.assertEqual(self.reset(token).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/refresh").status_code, 401)
        self.assertEqual(self.reset(token).status_code, 400)
        for password, status in [(TEST_PASSWORD, 401), ("New8char", 200)]:
            self.assertEqual(self.client.post("/api/auth/login", json={"email": self.user.email, "password": password}).status_code, status)
        self.db.expire_all()
        self.assertTrue(self.user.is_owner)
        self.assertEqual(self.user.role, "Admin")

    def test_expiry_account_changes_and_password_validation(self):
        self.request_link()
        token = self.token()
        self.assertEqual(self.reset(token, "short7!").status_code, 422)
        stored = self.db.scalar(select(PasswordResetToken))
        stored.expires_at = now() - timedelta(seconds=1)
        self.db.commit()
        expired = self.reset(token)
        self.assertEqual(expired.status_code, 400)
        stored.expires_at = now() + timedelta(minutes=15)
        self.user.version += 1
        self.db.commit()
        self.assertEqual(self.reset(token).json(), expired.json())
        self.assertEqual(self.reset("x" * 43).json(), expired.json())

    def test_inactive_account_and_email_cooldown_are_generic(self):
        first = self.request_link()
        self.assertEqual(self.request_link().json(), first.json())
        self.assertEqual(len(self.mail), 1)
        self.user.is_owner = False
        self.user.admin_slot = 2
        self.user.is_active = False
        self.db.commit()
        self.assertEqual(self.reset().status_code, 400)
        with patch("app.services.password_recovery.now", return_value=now() + timedelta(seconds=61)):
            self.assertEqual(self.request_link().json(), first.json())
        self.assertEqual(len(self.mail), 1)

    def test_ip_limits_persist_and_reset_attempts_are_bounded(self):
        for number in range(10):
            self.assertEqual(self.request_link(f"absent{number}@example.test").status_code, 202)
        limited = self.request_link("another@example.test")
        self.assertEqual(limited.status_code, 429)
        self.assertGreater(int(limited.headers["retry-after"]), 0)
        for _ in range(20):
            self.assertEqual(self.reset("x" * 43).status_code, 400)
        self.assertEqual(self.reset("x" * 43).status_code, 429)

    def test_failed_smtp_consumes_token_without_exposing_exception(self):
        with patch("app.services.password_recovery.send_reset_message", side_effect=RuntimeError("secret address link")), self.assertLogs("app.services.password_recovery", level="WARNING") as logs:
            self.assertEqual(self.request_link().status_code, 202)
        self.assertNotIn("secret address link", " ".join(logs.output))
        self.db.expire_all()
        stored = self.db.scalar(select(PasswordResetToken))
        self.assertEqual(stored.delivery_status, "failed")
        self.assertIsNotNone(stored.consumed_at)

    def test_disabled_and_csrf_checks(self):
        with patch.object(settings, "PASSWORD_RECOVERY_ENABLED", False):
            self.assertEqual(self.request_link().status_code, 503)
            self.assertEqual(self.reset("x" * 43).status_code, 503)
        self.assertEqual(self.request_link(headers={"Origin": "https://attacker.test"}).status_code, 403)
        del self.client.headers["X-CRM-Request"]
        self.assertEqual(self.request_link().status_code, 403)

    def test_smtp_uses_verified_tls_and_configuration_requires_trusted_url(self):
        from app.services.mailer import send_reset_message
        with patch.object(settings, "SMTP_PASSWORD", SecretStr("test-secret")), patch("app.services.mailer.smtplib.SMTP") as smtp:
            send_reset_message("owner@example.test", "https://crm.example.test/#reset-password?token=test", 15)
            server = smtp.return_value.__enter__.return_value
            self.assertTrue(server.starttls.call_args.kwargs["context"].check_hostname)
            server.login.assert_called_once()
            server.send_message.assert_called_once()
        valid = dict(DATABASE_URL="sqlite://", PASSWORD_RECOVERY_ENABLED=True, SMTP_HOST="smtp.example.test", SMTP_USERNAME="mailbox", SMTP_PASSWORD="secret", SMTP_FROM="crm@example.test")
        self.assertTrue(Settings(_env_file=None, **valid).PASSWORD_RECOVERY_ENABLED)
        for changes in [{"SMTP_HOST": ""}, {"RESET_BASE_URL": "https://attacker.test"}, {"SMTP_SECURITY": "none"}, {"SMTP_FROM_NAME": "Bad\r\nSender"}]:
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, **{**valid, **changes})
