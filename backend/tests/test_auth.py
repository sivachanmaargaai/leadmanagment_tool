import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.security import COOKIE_NAME, now, passwords, token_hash, utc
from app.db.database import Base, get_db
from app.main import app
from app.models.user import AccessToken, AuthSession, RefreshToken, User
from auth_helpers import isolate_request_limits, TEST_PASSWORD, test_password_hash


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'auth.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="admin@example.test", name="Test Admin", role="Admin", password_hash=test_password_hash())
        self.db.add(self.user)
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app)
        self.client.headers["X-CRM-Request"] = "1"

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def login(self, **changes):
        result = self.client.post("/api/auth/login", json={"email": "admin@example.test", "password": TEST_PASSWORD, **changes})
        self.assertEqual(result.status_code, 200, result.status_code)
        return result

    def auth_header(self, data):
        return {"Authorization": "Bearer " + data["accessToken"]}

    def test_all_business_routers_and_database_health_require_authentication(self):
        for path in ["/api/leads", "/api/customers", "/api/follow-ups", "/api/follow-ups/upcoming", "/api/follow-ups/overdue",
                     "/api/quotations", "/api/quotations/missing/pdf", "/api/reports/summary", "/api/reports/leads",
                     "/api/reports/sales", "/api/reports/follow-ups", "/api/db-health", "/api/auth/me"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.post("/api/leads", json={"customer": "A", "division": "MMC", "description": "IoT"}).status_code, 401)
        self.assertEqual(self.client.delete("/api/leads/missing").status_code, 401)
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        for path, methods in schema["paths"].items():
            if path.startswith("/api/") and not path.startswith("/api/auth/") and path not in {"/api/health", "/api/ready"}:
                for operation in methods.values():
                    self.assertTrue(operation.get("security"), path)

    def test_login_returns_safe_profile_and_only_hashed_tokens_are_stored(self):
        result = self.login(email=" ADMIN@EXAMPLE.TEST ")
        data = result.json()
        self.assertEqual(data["tokenType"], "Bearer")
        self.assertEqual(data["expiresIn"], 900)
        self.assertEqual(data["user"]["email"], "admin@example.test")
        self.assertNotIn("password_hash", data["user"])
        self.assertNotIn("refreshToken", data)
        cookie = result.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertIn("Path=/api/auth", cookie)
        self.assertEqual(result.headers["cache-control"], "no-store")
        raw_refresh = self.client.cookies.get(COOKIE_NAME)
        self.assertEqual(self.db.scalar(select(AccessToken)).token_hash, token_hash(data["accessToken"]))
        self.assertEqual(self.db.scalar(select(RefreshToken)).token_hash, token_hash(raw_refresh))
        self.assertNotEqual(self.user.password_hash, TEST_PASSWORD)
        self.assertTrue(self.user.password_hash.startswith("$argon2id$"))
        profile = self.client.get("/api/auth/me", headers=self.auth_header(data))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(set(profile.json()), {"id", "email", "name", "role", "isActive", "isOwner", "version", "canAccessQuotations"})

    def test_wrong_missing_and_inactive_accounts_have_generic_errors(self):
        responses = []
        for email, password in [("admin@example.test", "wrong password"), ("missing@example.test", TEST_PASSWORD)]:
            responses.append(self.client.post("/api/auth/login", json={"email": email, "password": password}))
        self.user.is_active = False
        self.db.commit()
        responses.append(self.client.post("/api/auth/login", json={"email": "admin@example.test", "password": TEST_PASSWORD}))
        self.assertTrue(all(x.status_code == 401 for x in responses))
        self.assertTrue(all(x.json() == responses[0].json() for x in responses))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AuthSession)), 0)

    def test_expired_access_can_refresh_without_extending_absolute_session_lifetime(self):
        original = self.login().json()
        raw_refresh = self.client.cookies.get(COOKIE_NAME)
        session = self.db.scalar(select(AuthSession))
        expiry = utc(session.expires_at)
        token = self.db.scalar(select(AccessToken))
        token.expires_at = now() - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(original)).status_code, 401)
        renewed = self.client.post("/api/auth/refresh")
        self.assertEqual(renewed.status_code, 200)
        self.assertNotEqual(renewed.json()["accessToken"], original["accessToken"])
        self.assertNotEqual(self.client.cookies.get(COOKIE_NAME), raw_refresh)
        self.assertEqual(utc(self.db.scalar(select(AuthSession)).expires_at), expiry)
        self.assertIsNotNone(self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw_refresh))).consumed_at)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(renewed.json())).status_code, 200)

    def test_used_refresh_token_replay_revokes_its_session(self):
        self.login()
        old_refresh = self.client.cookies.get(COOKIE_NAME)
        renewed = self.client.post("/api/auth/refresh").json()
        second_session = self.login().json()
        replay = self.client.post("/api/auth/refresh", headers={"Cookie": f"{COOKIE_NAME}={old_refresh}"})
        self.assertEqual(replay.status_code, 401)
        self.assertIn("Max-Age=0", replay.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(renewed)).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(second_session)).status_code, 200)

    def test_logout_revokes_one_session_and_logout_all_revokes_other_devices(self):
        first = self.login().json()
        first_cookie = self.client.cookies.get(COOKIE_NAME)
        second = self.login().json()
        headers = {**self.auth_header(first), "Cookie": f"{COOKIE_NAME}={first_cookie}"}
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(first)).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(second)).status_code, 200)
        third = self.login().json()
        self.assertEqual(self.client.post("/api/auth/logout-all", headers=self.auth_header(second)).status_code, 204)
        for data in [second, third]:
            self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(data)).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)

    def test_cookie_endpoints_require_csrf_header_and_allowlisted_origin(self):
        for path in ["login", "refresh", "logout", "logout-all"]:
            result = self.client.post("/api/auth/" + path, headers={"Origin": "https://untrusted.example"}, json={"email": "admin@example.test", "password": TEST_PASSWORD})
            self.assertEqual(result.status_code, 403)
        del self.client.headers["X-CRM-Request"]
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "admin@example.test", "password": TEST_PASSWORD}).status_code, 403)
        self.assertEqual(self.client.post("/api/auth/refresh").status_code, 403)
        self.client.headers["X-CRM-Request"] = "1"
        self.assertEqual(self.client.post("/api/auth/login", headers={"Origin": "http://localhost:5173"}, json={"email": "admin@example.test", "password": TEST_PASSWORD}).status_code, 200)

    def test_expired_session_or_disabled_user_cannot_refresh_or_access(self):
        data = self.login().json()
        session = self.db.scalar(select(AuthSession))
        session.expires_at = now() - timedelta(seconds=1)
        self.db.commit()
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(data)).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/refresh").status_code, 401)
        data = self.login().json()
        self.user.is_active = False
        self.db.commit()
        self.assertEqual(self.client.get("/api/auth/me", headers=self.auth_header(data)).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/refresh").status_code, 401)

    def test_tampered_tokens_and_password_whitespace(self):
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/refresh", headers={"Cookie": f"{COOKIE_NAME}=invalid"}).status_code, 401)
        self.user.password_hash = passwords.hash("  whitespace matters  ")
        self.db.commit()
        self.assertEqual(self.client.post("/api/auth/login", json={"email": self.user.email, "password": "whitespace matters"}).status_code, 401)
        self.login(password="  whitespace matters  ")
        self.assertEqual(self.client.post("/api/auth/login", json={"email": self.user.email, "password": "x" * 129}).status_code, 422)

    def test_secure_cookie_flag_and_production_configuration(self):
        with patch("app.routers.auth.settings.COOKIE_SECURE", True):
            result = self.login()
        self.assertIn("Secure", result.headers["set-cookie"])
        for config in [{"COOKIE_SECURE": False, "ALLOWED_ORIGINS": ["https://crm.example.test"]},
                       {"COOKIE_SECURE": True, "ALLOWED_ORIGINS": ["http://localhost:5173"]}]:
            with self.assertRaises(ValidationError):
                Settings(_env_file=None, DATABASE_URL="sqlite://", ENVIRONMENT="production", **config)
        valid = Settings(_env_file=None, DATABASE_URL="sqlite://", ENVIRONMENT="production", COOKIE_SECURE=True, ALLOWED_ORIGINS=["https://crm.example.test"])
        self.assertTrue(valid.COOKIE_SECURE)

    def test_admin_cli_creates_hash_without_overwriting_existing_users(self):
        from app.commands.create_admin import main
        factory = sessionmaker(bind=self.engine)
        with patch("app.commands.create_admin.SessionLocal", factory), patch("builtins.input", side_effect=["owner@example.test", "Owner"]), patch("app.commands.create_admin.getpass", return_value=TEST_PASSWORD), patch("builtins.print"):
            main()
        self.db.expire_all()
        owner = self.db.scalar(select(User).where(User.email == "owner@example.test"))
        self.assertEqual(owner.role, "Admin")
        self.assertTrue(passwords.verify(TEST_PASSWORD, owner.password_hash))
        original_hash = owner.password_hash
        with patch("app.commands.create_admin.SessionLocal", factory), patch("builtins.input", side_effect=["owner@example.test", "Owner"]), patch("app.commands.create_admin.getpass", return_value=TEST_PASSWORD), patch("builtins.print"), self.assertRaises(SystemExit):
            main()
        self.db.expire_all()
        self.assertEqual(self.db.get(User, owner.id).password_hash, original_hash)

    def test_admin_cli_accepts_eight_characters_and_rejects_seven(self):
        from app.commands.create_admin import main
        factory = sessionmaker(bind=self.engine)
        for password, accepted in [("Qa8char", False), ("Qa8chars", True)]:
            with patch("app.commands.create_admin.SessionLocal", factory), patch("builtins.input", side_effect=["eight@example.test", "Owner"]), patch("app.commands.create_admin.getpass", return_value=password), patch("builtins.print"):
                if accepted:
                    main()
                else:
                    with self.assertRaises(SystemExit):
                        main()
            self.db.expire_all()
            account = self.db.scalar(select(User).where(User.email == "eight@example.test"))
            if accepted:
                self.assertTrue(passwords.verify(password, account.password_hash))
            else:
                self.assertIsNone(account)
