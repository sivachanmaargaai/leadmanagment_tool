import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import passwords
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User, UserAuditEvent
from auth_helpers import isolate_request_limits, TEST_PASSWORD, test_password_hash


class UserManagementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'users.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner = User(name="Owner", email="owner@example.test", password_hash=test_password_hash(), role="Admin", is_owner=True, admin_slot=1)
        self.db.add(self.owner)
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app)
        self.client.headers["X-CRM-Request"] = "1"
        self.owner_headers = self.sign_in(self.owner.email)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def sign_in(self, email, password=TEST_PASSWORD):
        result = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(result.status_code, 200)
        return {"Authorization": "Bearer " + result.json()["accessToken"]}

    def create(self, email, role="Staff", **changes):
        result = self.client.post("/api/users", headers=self.owner_headers,
            json={"name": "Test " + role, "email": email, "password": TEST_PASSWORD, "role": role, **changes})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def modify(self, account, **changes):
        return self.client.put(f"/api/users/{account['id']}", headers=self.owner_headers,
                               json={"expectedVersion": account["version"], **changes})

    def test_01_owner_lists_all_real_accounts_and_new_staff_can_sign_in(self):
        staff = self.create(" STAFF@EXAMPLE.TEST ", name="  Staff User  ", password="Qa8chars")
        self.assertEqual(staff["email"], "staff@example.test")
        self.assertEqual(staff["name"], "Staff User")
        self.assertFalse(staff["isOwner"])
        headers = self.sign_in(staff["email"], "Qa8chars")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).json()["role"], "Staff")
        directory = self.client.get("/api/users", headers=self.owner_headers)
        self.assertEqual(directory.status_code, 200)
        data = directory.json()
        self.assertTrue(data["canManageUsers"])
        self.assertEqual(data["adminCount"], 1)
        self.assertEqual({x["id"] for x in data["users"]}, {self.owner.id, staff["id"]})
        self.assertNotIn("password", directory.text)
        self.assertEqual(directory.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/api/users").status_code, 401)

    def test_02_two_admin_limit_includes_inactive_accounts_and_freed_slot_can_be_reused(self):
        second = self.create("second@example.test", "Admin")
        staff = self.create("staff@example.test")
        denied = self.client.post("/api/users", headers=self.owner_headers,
            json={"name": "Third", "email": "third@example.test", "password": TEST_PASSWORD, "role": "Admin"})
        self.assertEqual(denied.status_code, 409)
        self.assertEqual(self.modify(staff, role="Admin").status_code, 409)
        second = self.modify(second, isActive=False).json()
        self.assertEqual(self.modify(staff, role="Admin").status_code, 409)
        self.assertEqual(self.modify(second, role="Staff").status_code, 200)
        promoted = self.modify(staff, role="Admin")
        self.assertEqual(promoted.status_code, 200, promoted.text)
        self.assertEqual(self.client.get("/api/users", headers=self.owner_headers).json()["adminCount"], 2)

    def test_03_second_admin_sees_staff_only_and_cannot_modify_any_accounts(self):
        second = self.create("second@example.test", "Admin")
        staff = self.create("staff@example.test")
        headers = self.sign_in(second["email"])
        directory = self.client.get("/api/users", headers=headers).json()
        self.assertEqual(directory["scope"], "Staff only")
        self.assertFalse(directory["canManageUsers"])
        self.assertEqual([x["id"] for x in directory["users"]], [staff["id"]])
        self.assertEqual(self.client.get(f"/api/users/{self.owner.id}", headers=headers).status_code, 404)
        self.assertEqual(self.client.get(f"/api/users/{staff['id']}", headers=headers).status_code, 200)
        self.assertEqual(self.client.put(f"/api/users/{staff['id']}", headers=headers, json={"expectedVersion": 1, "role": "Admin"}).status_code, 403)
        self.assertEqual(self.client.post("/api/users", headers=headers, json={"name": "Denied", "email": "denied@example.test", "password": TEST_PASSWORD}).status_code, 403)

    def test_04_staff_sees_only_own_profile_and_cannot_promote_or_create(self):
        staff = self.create("staff@example.test")
        another = self.create("another@example.test")
        headers = self.sign_in(staff["email"])
        directory = self.client.get("/api/users", headers=headers).json()
        self.assertEqual(directory["scope"], "My profile")
        self.assertEqual([x["id"] for x in directory["users"]], [staff["id"]])
        self.assertEqual(self.client.get(f"/api/users/{another['id']}", headers=headers).status_code, 404)
        self.assertEqual(self.client.put(f"/api/users/{staff['id']}", headers=headers, json={"expectedVersion": 1, "role": "Admin"}).status_code, 403)
        self.assertEqual(self.client.post("/api/users", headers=headers, json={"name": "Denied", "email": "denied@example.test", "password": TEST_PASSWORD}).status_code, 403)

    def test_05_owner_is_protected_and_sensitive_changes_revoke_sessions_with_safe_audit(self):
        for changes in [{"role": "Staff"}, {"isActive": False}, {"email": "changed@example.test"}, {"password": "newpassword"}]:
            self.assertEqual(self.client.put(f"/api/users/{self.owner.id}", headers=self.owner_headers, json={"expectedVersion": 1, **changes}).status_code, 403)
        staff = self.create("staff@example.test")
        old_session = self.sign_in(staff["email"])
        changed = self.modify(staff, password="Newpass8", name="Changed User")
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(self.client.get("/api/auth/me", headers=old_session).status_code, 401)
        self.assertEqual(self.modify(staff, name="Stale edit").status_code, 409)
        self.sign_in(staff["email"], "Newpass8")
        audit = self.db.scalars(select(UserAuditEvent).where(UserAuditEvent.target_id == staff["id"])).all()
        serialized = json.dumps([event.changes for event in audit])
        self.assertNotIn("Newpass8", serialized)
        self.assertNotIn("password_hash", serialized)
        self.assertTrue(all(event.actor_id == self.owner.id for event in audit))
        self.assertTrue(any(event.changes.get("sessionsRevoked") for event in audit))

    def test_06_invalid_payloads_duplicate_email_and_database_slot_constraint(self):
        staff = self.create("staff@example.test")
        for payload in [{"name": "Invalid", "email": "bad", "password": TEST_PASSWORD},
                        {"name": "Invalid", "email": "valid@example.test", "password": "7short"},
                        {"name": "Invalid", "email": "valid@example.test", "password": TEST_PASSWORD, "isOwner": True}]:
            self.assertEqual(self.client.post("/api/users", headers=self.owner_headers, json=payload).status_code, 422)
        self.assertEqual(self.client.post("/api/users", headers=self.owner_headers,
            json={"name": "Duplicate", "email": "STAFF@EXAMPLE.TEST", "password": TEST_PASSWORD}).status_code, 409)
        self.assertEqual(self.modify(staff, isActive=None).status_code, 422)
        self.create("second@example.test", "Admin")
        self.db.add(User(name="Raw third", email="raw@example.test", role="Admin", admin_slot=2, password_hash=test_password_hash()))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


class OwnerMigrationTests(unittest.TestCase):
    @contextmanager
    def old_database(self, admin_count):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'migration.db'}")
            try:
                with engine.begin() as connection:
                    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
                    config.attributes["connection"] = connection
                    command.upgrade(config, "20261104_0004")
                    for i in range(admin_count):
                        connection.execute(text("INSERT INTO users (id,email,name,password_hash,role,is_active,created_at) VALUES (:id,:email,:name,:hash,'Admin',:active,:created)"),
                            {"id": f"admin-{i}", "email": f"admin{i}@example.test", "name": f"Admin {i}", "hash": "existing-hash-unchanged", "active": True, "created": f"2026-01-0{i + 1} 00:00:00"})
                    yield connection, config
            finally:
                engine.dispose()

    def test_first_existing_admin_becomes_owner_without_changing_credentials(self):
        with self.old_database(2) as (connection, config):
            command.upgrade(config, "head")
            rows = connection.execute(text("SELECT id,is_owner,admin_slot,password_hash FROM users ORDER BY created_at")).mappings().all()
            self.assertEqual(len(rows), 2)
            self.assertTrue(rows[0]["is_owner"])
            self.assertEqual(rows[0]["admin_slot"], 1)
            self.assertFalse(rows[1]["is_owner"])
            self.assertEqual(rows[1]["admin_slot"], 2)
            self.assertTrue(all(x["password_hash"] == "existing-hash-unchanged" for x in rows))

    def test_excess_existing_admins_stop_migration_without_demoting_anyone(self):
        with self.old_database(3) as (connection, config):
            with self.assertRaisesRegex(RuntimeError, "More than two"):
                command.upgrade(config, "head")
            self.assertEqual(connection.execute(text("SELECT count(*) FROM users WHERE role='Admin'")).scalar(), 3)
            self.assertNotIn("is_owner", {x["name"] for x in inspect(connection).get_columns("users")})
