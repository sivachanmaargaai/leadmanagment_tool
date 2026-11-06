import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.role_permissions import RolePermissions
from auth_helpers import isolate_request_limits, TEST_PASSWORD, test_password_hash


class CrmAccessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'access.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        # Row-scope tests explicitly grant the module; default-deny is covered separately.
        self.accounts = [User(email=f"access{number}@example.test", name="Same Name" if number > 1 else f"Admin {number}",
                              role="Admin" if number < 2 else "Staff", quotation_access=number > 1, is_owner=number == 0,
                              admin_slot=number + 1 if number < 2 else None, password_hash=test_password_hash()) for number in range(4)]
        self.db.add(RolePermissions(role="Staff", quotations=True))
        self.db.add_all(self.accounts)
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app, headers={"X-CRM-Request": "1"})
        self.headers = []
        for user in self.accounts:
            result = self.client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
            self.assertEqual(result.status_code, 200)
            self.headers.append({"Authorization": "Bearer " + result.json()["accessToken"]})
        self.client.headers.update(self.headers[0])

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def lead(self, name="Embedded prospect"):
        result = self.client.post("/api/leads", json={"customer": name, "division": "MMC", "description": "IoT firmware"})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def customer(self):
        result = self.client.post("/api/customers", json={"name": "Embedded prospect", "divisions": ["MMC"], "contacts": [{"phone": "1234567890"}]})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def quote(self):
        result = self.client.post("/api/quotations", json={"number": "ACCESS-001", "customer": "Embedded prospect", "division": "MMC", "date": "2026-11-05", "validUntil": "2026-12-05", "items": [{"description": "Firmware", "quantity": 1, "rate": 100, "billing": "One-time"}]})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def assign(self, module, record, target=2, headers=None):
        return self.client.put(f"/api/access/assignments/{module}/{record['id']}", json={"assigneeUserId": self.accounts[target].id if target is not None else None,
                           "expectedAssigneeUserId": record["assigneeUserId"], "expectedVersion": record["version"]}, headers=headers or self.headers[0])

    def test_staff_lists_details_updates_and_assignment_forgery(self):
        lead = self.lead()
        self.assertEqual(self.client.get("/api/leads", headers=self.headers[2]).json(), [])
        self.assertEqual(self.assign("leads", lead).status_code, 200)
        self.assertEqual([x["id"] for x in self.client.get("/api/leads", headers=self.headers[2]).json()], [lead["id"]])
        for method, payload in [("get", None), ("put", {"priority": "High"})]:
            kwargs = {"json": payload} if payload else {}
            self.assertEqual(getattr(self.client, method)(f"/api/leads/{lead['id']}", headers=self.headers[3], **kwargs).status_code, 404)
        self.assertEqual(self.client.put(f"/api/leads/{lead['id']}", headers=self.headers[2], json={"priority": "High", "expectedVersion": 2}).status_code, 200)
        self.assertEqual(self.client.put(f"/api/leads/{lead['id']}", headers=self.headers[2], json={"assigneeUserId": self.accounts[3].id}).status_code, 422)
        self.assertEqual(self.assign("leads", lead, headers=self.headers[2]).status_code, 403)
        self.assertNotIn("crm_actor", self.db.info)

    def test_staff_creation_is_self_assigned_and_deletions_denied(self):
        self.client.headers.update(self.headers[2])
        lead, customer, quote = self.lead(), self.customer(), self.quote()
        for module, record in [("leads", lead), ("customers", customer), ("quotations", quote)]:
            self.assertEqual(record["assigneeUserId"], self.accounts[2].id)
            self.assertEqual(self.client.get(f"/api/{module}/{record['id']}", headers=self.headers[3]).status_code, 404)
            suffix = "?expectedVersion=1" if module == "quotations" else ""
            self.assertEqual(self.client.delete(f"/api/{module}/{record['id']}" + suffix).status_code, 403)
        self.assertEqual(customer["assignedTo"], self.accounts[2].name)
        self.assertEqual(self.client.get("/api/access/assignments").status_code, 403)

    def test_followups_inherit_lead_access_and_reassignment(self):
        lead = self.lead()
        self.assign("leads", lead)
        result = self.client.post("/api/follow-ups", headers=self.headers[2], json={"leadId": lead["id"], "purpose": "Call", "dueAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "assignedTo": "Someone else"})
        self.assertEqual(result.status_code, 201, result.text)
        task = result.json()
        self.assertEqual(task["assignedTo"], self.accounts[2].name)
        for path in ["/api/follow-ups", "/api/follow-ups/upcoming", "/api/follow-ups/overdue"]:
            self.assertEqual(self.client.get(path, headers=self.headers[3]).json(), [])
        self.assertEqual(self.client.put(f"/api/follow-ups/{task['id']}", headers=self.headers[3], json={"notes": "Hacked"}).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/follow-ups/{task['id']}", headers=self.headers[2]).status_code, 403)
        current = {**lead, "assigneeUserId": self.accounts[2].id, "version": 2}
        self.assertEqual(self.assign("leads", current, 3).status_code, 200)
        self.assertEqual(self.client.get(f"/api/follow-ups/{task['id']}", headers=self.headers[2]).status_code, 404)
        self.assertEqual(self.client.get(f"/api/follow-ups/{task['id']}", headers=self.headers[3]).status_code, 200)
        self.assertEqual(self.client.post("/api/follow-ups", headers=self.headers[2], json={"leadId": lead["id"], "purpose": "Call", "dueAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}).status_code, 404)

    def test_quote_pdf_versions_and_customer_profiles_do_not_leak_by_name(self):
        lead, customer, quote = self.lead(), self.customer(), self.quote()
        self.assign("leads", lead)
        self.assertEqual(self.client.get("/api/customers", headers=self.headers[2]).json(), [])
        self.assertEqual(self.client.get("/api/quotations", headers=self.headers[2]).json(), [])
        for path in [f"/api/customers/{customer['id']}", f"/api/quotations/{quote['id']}", f"/api/quotations/{quote['id']}/pdf", quote["versions"][0]["pdfPath"]]:
            self.assertEqual(self.client.get(path, headers=self.headers[2]).status_code, 404)
        self.assign("customers", customer)
        self.assign("quotations", quote)
        self.assertEqual(self.client.get(f"/api/customers/{customer['id']}", headers=self.headers[2]).status_code, 200)
        self.assertEqual(self.client.get(quote["versions"][0]["pdfPath"], headers=self.headers[2]).status_code, 200)
        self.assertEqual(self.client.get(quote["versions"][0]["pdfPath"], headers=self.headers[3]).status_code, 404)
        self.assertEqual(self.client.put(f"/api/quotations/{quote['id']}", headers=self.headers[3], json={"expectedVersion": 2, "status": "Sent"}).status_code, 404)

    def test_reports_and_summary_only_count_accessible_records(self):
        lead, quote = self.lead(), self.quote()
        self.assign("leads", lead)
        self.assign("quotations", quote)
        for number, total in [(2, 1), (3, 0), (0, 1), (1, 1)]:
            report = self.client.get("/api/reports/summary", headers=self.headers[number]).json()
            self.assertEqual(report["totals"]["totalLeads"], total)
            self.assertEqual(report["totals"]["totalQuotations"], total)
            for path in ["leads", "sales"]:
                self.assertEqual(len(self.client.get("/api/reports/" + path, headers=self.headers[number]).json()["rows"]), total)

    def test_admin_reassignment_conflicts_inactive_users_and_unassignment(self):
        lead = self.lead()
        self.assertEqual(self.assign("leads", lead, headers=self.headers[1]).status_code, 200)
        self.assertEqual(self.assign("leads", lead, 3).status_code, 409)
        current = {**lead, "assigneeUserId": self.accounts[2].id, "version": 2}
        self.accounts[3].is_active = False
        self.db.commit()
        self.assertEqual(self.assign("leads", current, 3).status_code, 422)
        self.assertEqual(self.assign("leads", current, None).status_code, 200)
        self.assertEqual(self.client.get("/api/leads", headers=self.headers[2]).json(), [])
        self.assertEqual(len(self.client.get("/api/leads", headers=self.headers[1]).json()), 1)
        self.assertEqual(self.client.get("/api/access/assignments?limit=101").status_code, 422)
        directory = self.client.get("/api/access/assignments").json()
        self.assertNotIn("email", directory["users"][0])
