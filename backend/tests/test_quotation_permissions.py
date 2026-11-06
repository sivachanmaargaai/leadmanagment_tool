import unittest
from sqlalchemy import select
from app.models.user import User, UserAuditEvent
from app.models.role_permissions import RolePermissions
import test_crm_access as fixtures


class QuotationPermissionTests(unittest.TestCase):
    tearDown = fixtures.CrmAccessTests.tearDown
    lead = fixtures.CrmAccessTests.lead
    customer = fixtures.CrmAccessTests.customer
    quote = fixtures.CrmAccessTests.quote
    assign = fixtures.CrmAccessTests.assign

    def setUp(self):
        fixtures.CrmAccessTests.setUp(self)
        self.db.get(RolePermissions, "Staff").quotations = False
        self.db.commit()

    def sign_in(self, number):
        from auth_helpers import TEST_PASSWORD
        response = self.client.post("/api/auth/login", json={"email": self.accounts[number].email, "password": TEST_PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        self.headers[number] = {"Authorization": "Bearer " + response.json()["accessToken"]}
        return response.json()

    def access(self, enabled, admin=0, version=None):
        current = self.client.get("/api/permissions", headers=self.headers[0]).json()
        return self.client.put("/api/permissions/staff", headers=self.headers[admin],
            json={"quotations": enabled, "expectedVersion": version or current["version"]})

    def test_default_off_ignores_legacy_individual_grants_and_admins_keep_access(self):
        self.assertTrue(self.accounts[2].quotation_access)
        self.assertFalse(self.sign_in(2)["user"]["canAccessQuotations"])
        for number in [0, 1]:
            self.assertTrue(self.sign_in(number)["user"]["canAccessQuotations"])
            self.assertEqual(self.client.get("/api/quotations", headers=self.headers[number]).status_code, 200)
        self.assertEqual(self.client.get("/api/permissions", headers=self.headers[2]).status_code, 403)
        self.assertEqual(self.client.put(f"/api/users/{self.accounts[2].id}/quotation-access", json={"enabled": True, "expectedVersion": 1}).status_code, 410)

    def test_disabled_staff_cannot_access_any_quotation_or_pdf_route(self):
        quote = self.quote(); self.assign("quotations", quote)
        paths = ["/api/quotations", "/api/quotations?paged=true&summary=true", f"/api/quotations/{quote['id']}", f"/api/quotations/{quote['id']}/pdf", f"/api/quotations/{quote['id']}/pdf?download=true", quote["versions"][0]["pdfPath"], "/api/reports/sales"]
        for path in paths:
            self.assertEqual(self.client.get(path, headers=self.headers[2]).status_code, 403, path)
        for path in ["/api/quotations", "/api/quotations/upload", f"/api/quotations/{quote['id']}/revisions"]:
            self.assertEqual(self.client.post(path, headers=self.headers[2], json={}).status_code, 403)
        self.assertEqual(self.client.put(f"/api/quotations/{quote['id']}", headers=self.headers[2], json={"status": "Sent", "expectedVersion": 2}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/quotations/{quote['id']}?expectedVersion=2", headers=self.headers[2]).status_code, 403)

    def test_no_quote_data_in_settings_dashboard_reports_or_customer_activity(self):
        quote = self.quote(); self.assign("quotations", quote)
        summary = self.client.get("/api/reports/summary", headers=self.headers[2]).json()
        for name in ["totalQuotations", "acceptedQuotations"]:
            self.assertNotIn(name, summary["totals"])
        self.assertNotIn("acceptedValue", summary)
        overview = self.client.get("/api/workspace/overview?quotationExpiry=true", headers=self.headers[2]).json()
        self.assertNotIn("alertQuotes", overview)
        self.assertNotIn("quotations", overview["metrics"])
        saved = self.client.get("/api/settings", headers=self.headers[2]).json()
        self.assertNotIn("quotation", saved)
        self.assertFalse(saved["notifications"]["quotationExpiry"])
        for module in ["leads", "follow-ups", "customers"]:
            self.assertEqual(self.client.get(f"/api/{module}", headers=self.headers[2]).status_code, 200)

    def test_both_admins_change_all_staff_together_without_bypassing_assignments(self):
        quote = self.quote(); self.assign("quotations", quote)
        for admin in [0, 1]:
            granted = self.access(True, admin)
            self.assertEqual(granted.status_code, 200, granted.text)
            for staff in [2, 3]:
                self.assertEqual(self.client.get("/api/auth/me", headers=self.headers[staff]).status_code, 401)
                self.assertTrue(self.sign_in(staff)["user"]["canAccessQuotations"])
            self.assertEqual(self.client.get(quote["versions"][0]["pdfPath"], headers=self.headers[2]).status_code, 200)
            self.assertEqual(self.client.get(quote["versions"][0]["pdfPath"], headers=self.headers[3]).status_code, 404)
            self.assertEqual(self.access(False, admin).status_code, 200)
            for staff in [2, 3]:
                self.assertEqual(self.client.get("/api/auth/me", headers=self.headers[staff]).status_code, 401)
                self.assertFalse(self.sign_in(staff)["user"]["canAccessQuotations"])
            for admin_number in [0, 1]:
                self.assertEqual(self.client.get("/api/auth/me", headers=self.headers[admin_number]).status_code, 200)

    def test_global_permission_is_versioned_audited_and_staff_cannot_self_grant(self):
        self.assertEqual(self.access(True, admin=2).status_code, 403)
        before = self.client.get("/api/permissions").json()
        grant = self.access(True, admin=1)
        self.assertEqual(grant.status_code, 200)
        self.assertEqual(self.access(False, version=before["version"]).status_code, 409)
        audit = self.db.scalar(select(UserAuditEvent).where(UserAuditEvent.action == "Role permissions changed"))
        self.assertEqual(audit.actor_id, self.accounts[1].id)
        self.assertEqual(audit.changes, {"role": "Staff", "before": {"quotations": False}, "after": {"quotations": True}, "staffSessionsRevoked": True})
        self.assertEqual(self.client.put("/api/permissions/staff", json={"quotations": True, "expectedVersion": grant.json()["version"], "Admin": False}).status_code, 422)
        self.assertEqual(self.client.put(f"/api/users/{self.accounts[3].id}", json={"expectedVersion": 1, "quotation_access": True}).status_code, 422)

    def test_new_staff_and_demoted_admin_inherit_the_common_staff_policy(self):
        from auth_helpers import TEST_PASSWORD
        self.assertEqual(self.access(True).status_code, 200)
        created = self.client.post("/api/users", json={"name": "New Staff", "email": "new@example.test", "password": TEST_PASSWORD})
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["canAccessQuotations"])
        second = self.client.get(f"/api/users/{self.accounts[1].id}").json()
        demoted = self.client.put(f"/api/users/{second['id']}", json={"expectedVersion": second["version"], "role": "Staff"})
        self.assertEqual(demoted.status_code, 200)
        self.assertTrue(demoted.json()["canAccessQuotations"])
        self.assertEqual(self.access(False).status_code, 200)
        self.assertFalse(self.sign_in(1)["user"]["canAccessQuotations"])
        self.assertTrue(self.client.get("/api/auth/me", headers=self.headers[0]).json()["canAccessQuotations"])

    def test_migration_preserves_accounts_and_sessions_and_starts_common_role_off(self):
        from pathlib import Path
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine, MetaData
        from app.models.user import AuthSession
        engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'role-migration.db'}")
        config = Config("alembic.ini")
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "20261106_0012")
            metadata = MetaData(); metadata.reflect(connection)
            for model in [User, AuthSession]:
                for row in self.db.execute(select(model.__table__)).mappings():
                    connection.execute(metadata.tables[model.__tablename__].insert().values(**dict(row)))
            before = connection.execute(select(metadata.tables["users"]).order_by(metadata.tables["users"].c.id)).all()
            sessions = connection.execute(select(metadata.tables["auth_sessions"])).mappings().all()
            command.upgrade(config, "head")
            current = MetaData(); current.reflect(connection)
            policy = connection.execute(select(current.tables["role_permissions"])).mappings().one()
            self.assertEqual((policy["role"], policy["quotations"], policy["version"]), ("Staff", False, 1))
            self.assertEqual(before, connection.execute(select(current.tables["users"]).order_by(current.tables["users"].c.id)).all())
            after_sessions = {row["id"]: row for row in connection.execute(select(current.tables["auth_sessions"])).mappings()}
            staff_ids = {account.id for account in self.accounts[2:]}
            for before_session in sessions:
                after_session = after_sessions[before_session["id"]]
                self.assertEqual({key: value for key, value in before_session.items() if key != "revoked_at"}, {key: value for key, value in after_session.items() if key != "revoked_at"})
                if before_session["user_id"] in staff_ids:
                    self.assertIsNotNone(after_session["revoked_at"])
                else:
                    self.assertEqual(before_session["revoked_at"], after_session["revoked_at"])
            command.downgrade(config, "20261106_0012")
        engine.dispose()
