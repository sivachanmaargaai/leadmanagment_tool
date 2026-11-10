import os
import tempfile
import unittest
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.role_permissions import RolePermissions
from auth_helpers import isolate_request_limits, TEST_PASSWORD, test_password_hash


class SettingsScenarios(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'settings.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner = User(name="Owner", email="owner@example.test", password_hash=test_password_hash(), role="Admin", is_owner=True, admin_slot=1)
        self.staff = User(name="Staff", email="staff@example.test", password_hash=test_password_hash(), role="Staff", quotation_access=True)
        self.db.add(RolePermissions(role="Staff", quotations=True))
        self.db.add_all([self.owner, self.staff])
        self.db.commit()
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app)
        self.client.headers["X-CRM-Request"] = "1"
        self.owner_headers = self.login("owner@example.test")
        self.staff_headers = self.login("staff@example.test")

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def login(self, email, password=TEST_PASSWORD):
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": "Bearer " + response.json()["accessToken"]}

    def settings(self, headers=None):
        response = self.client.get("/api/settings", headers=headers or self.owner_headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def save(self, changes, headers=None, expected=200):
        response = self.client.put("/api/settings", headers=headers or self.owner_headers, json=changes)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if expected != 204 else None

    def test_01_shared_settings_persist_and_only_owner_can_modify_them(self):
        initial = self.settings()
        self.assertTrue(initial["canManageShared"])
        self.assertEqual(set(initial["divisions"]), {"MMC", "nemilink", "ClearCode Labs", "ENGEN", "Visotonics", "Overview"})
        self.assertEqual({name: item["prefix"] for name, item in initial["divisions"].items()},
                         {"MMC": "MMC", "nemilink": "NEM", "ClearCode Labs": "CCL", "ENGEN": "ENG", "Visotonics": "VIS", "Overview": "OVW"})
        divisions = initial["divisions"]
        divisions["MMC"].update(gst="QA-GST", address="QA division address", prefix="HW")
        saved = self.save({"expectedSharedVersion": 1, "company": {"name": "QA Engineering", "email": "office@example.test", "website": "https://example.test"}, "divisions": divisions})
        self.db.expire_all()
        self.assertEqual(self.settings()["company"]["name"], "QA Engineering")
        self.assertEqual(saved["versions"]["shared"], 2)
        self.assertEqual(self.client.get("/api/settings/divisions", headers=self.staff_headers).json()[0]["prefix"], "HW")
        self.assertFalse(self.settings(self.staff_headers)["canManageShared"])
        self.save({"expectedSharedVersion": 2, "company": {"name": "Forbidden"}}, self.staff_headers, 403)
        self.assertEqual(self.client.get("/api/settings").status_code, 401)
        self.assertEqual(self.client.put("/api/settings", json={"expectedSharedVersion": 2, "leads": initial["leads"]}).status_code, 401)
        self.save({"expectedSharedVersion": 2, "company": {"name": "Invalid", "website": "javascript:bad"}}, expected=422)
        self.save({"expectedSharedVersion": 2, "divisions": {"Unknown": {"name": "MMC"}}}, expected=422)

    def test_new_divisions_are_valid_for_leads_quotations_and_workspace_defaults(self):
        initial = self.settings()
        prefs = {**initial["workspace"], "defaultDivision": "Overview"}
        saved = self.save({"expectedPersonalVersion": 0, "workspace": prefs})
        self.assertEqual(saved["workspace"]["defaultDivision"], "Overview")

        for division, prefix in [("ENGEN", "ENG"), ("Visotonics", "VIS"), ("Overview", "OVW")]:
            lead = self.client.post("/api/leads", headers=self.owner_headers, json={
                "customer": f"{division} API customer", "division": division, "description": "Division validation check",
            })
            self.assertEqual(lead.status_code, 201, lead.text)
            quote = self.client.post("/api/quotations", headers=self.owner_headers, json={
                "customer": f"{division} API customer", "division": division, "date": "2026-11-10",
                "items": [{"description": "IoT integration", "quantity": 1, "rate": 100}],
            })
            self.assertEqual(quote.status_code, 201, quote.text)
            self.assertTrue(quote.json()["number"].startswith(f"{prefix}-2026-"), quote.json()["number"])

    def test_02_personal_profile_preferences_are_isolated_and_password_change_revokes_sessions(self):
        initial = self.settings()
        workspace = {**initial["workspace"], "rowsPerPage": 25, "dateFormat": "YYYY-MM-DD", "sidebar": "Always expanded", "defaultDivision": "nemilink"}
        saved = self.save({"expectedPersonalVersion": 0, "expectedProfileVersion": 1,
            "profile": {"name": "Updated Owner", "phone": "QA phone", "designation": "Director"}, "workspace": workspace,
            "notifications": {**initial["notifications"], "sound": True, "reminderBefore": 120, "overdue": False}})
        self.assertEqual(saved["profile"]["name"], "Updated Owner")
        self.assertEqual(saved["versions"]["profile"], 2)
        other = self.settings(self.staff_headers)
        self.assertEqual(other["workspace"]["rowsPerPage"], 10)
        self.assertEqual(other["profile"]["phone"], "")
        self.assertTrue(other["notifications"]["overdue"])
        self.save({"expectedPersonalVersion": 0, "workspace": {**other["workspace"], "rowsPerPage": 50}}, self.staff_headers)
        self.assertEqual(self.settings()["workspace"]["rowsPerPage"], 25)
        self.save({"expectedPersonalVersion": 1, "expectedProfileVersion": 1, "profile": {"name": "Forged", "email": "changed@example.test"}}, self.staff_headers, 422)
        wrong = self.client.post("/api/auth/change-password", headers=self.owner_headers, json={"currentPassword": "wrong", "newPassword": "Newpass8"})
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.owner_headers).status_code, 200)
        changed = self.client.post("/api/auth/change-password", headers=self.owner_headers, json={"currentPassword": TEST_PASSWORD, "newPassword": "Newpass8"})
        self.assertEqual(changed.status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.owner_headers).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"email": "owner@example.test", "password": TEST_PASSWORD}).status_code, 401)
        self.login("owner@example.test", "Newpass8")

    def test_03_stale_combined_save_rolls_back_shared_and_personal_changes(self):
        initial = self.settings()
        self.save({"expectedPersonalVersion": 0, "workspace": {**initial["workspace"], "rowsPerPage": 25}})
        self.save({"expectedSharedVersion": 1, "expectedPersonalVersion": 0, "company": {"name": "Must roll back"}, "workspace": {**initial["workspace"], "rowsPerPage": 50}}, expected=409)
        current = self.settings()
        self.assertEqual(current["company"]["name"], "ENGEN")
        self.assertEqual(current["workspace"]["rowsPerPage"], 25)
        self.assertEqual(current["versions"]["shared"], 1)
        self.save({"expectedSharedVersion": 1, "company": {"name": "Saved"}})
        self.save({"expectedSharedVersion": 1, "company": {"name": "Stale"}}, expected=409)
        self.assertEqual(self.settings()["company"]["name"], "Saved")

    def test_04_lead_defaults_and_required_fields_are_enforced_by_backend(self):
        initial = self.settings()
        saved = self.save({"expectedSharedVersion": 1, "leads": {**initial["leads"], "defaultPriority": "High", "defaultStatus": "Follow-up", "sources": ["Partner"], "requireContact": True, "requireDescription": False}})
        denied = self.client.post("/api/leads", headers=self.staff_headers, json={"customer": "QA Lead", "division": "MMC"})
        self.assertEqual(denied.status_code, 422)
        lead = self.client.post("/api/leads", headers=self.staff_headers, json={"customer": "QA Lead", "contact": "QA Contact", "division": "MMC"})
        self.assertEqual(lead.status_code, 201, lead.text)
        self.assertEqual((lead.json()["priority"], lead.json()["status"], lead.json()["description"]), ("High", "Follow-up", ""))
        self.save({"expectedSharedVersion": saved["versions"]["shared"], "leads": {**saved["leads"], "requireDescription": True}})
        self.assertEqual(self.client.put(f"/api/leads/{lead.json()['id']}", headers=self.staff_headers, json={"priority": "Low", "expectedVersion": 1}).status_code, 200)
        self.assertEqual(self.client.put(f"/api/leads/{lead.json()['id']}", headers=self.staff_headers, json={"description": "", "expectedVersion": 2}).status_code, 422)

    def test_05_quote_defaults_numbering_pdf_snapshot_and_owner_approval(self):
        initial = self.settings()
        divisions = initial["divisions"]
        divisions["MMC"].update(prefix="HW", address="Division address", gst="QA-GST")
        self.save({"expectedSharedVersion": 1, "company": {"name": "QA Engineering"}, "divisions": divisions,
            "quotation": {**initial["quotation"], "currency": "USD", "validity": 7, "tax": 18, "paymentTerms": "QA payment terms", "showLogo": False, "showSignature": True, "approvalRequired": True}})
        payload = {"customer": "QA Customer", "division": "MMC", "date": "2026-11-04", "items": [{"description": "IoT device", "quantity": 1, "rate": 100}]}
        first = self.client.post("/api/quotations", headers=self.staff_headers, json=payload)
        self.assertEqual(first.status_code, 201, first.text)
        quote = first.json()
        self.assertEqual(quote["number"], "HW-2026-01001")
        self.assertEqual(quote["validUntil"], str(date(2026, 11, 4) + timedelta(days=7)))
        self.assertEqual(quote["currency"], "USD")
        self.assertEqual(quote["totals"]["One-time"]["total"], 118)
        pdf = self.client.get(quote["versions"][0]["pdfPath"], headers=self.owner_headers).content
        document_text = " ".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
        for value in ["QA Engineering", "Division address", "QA-GST", "QA payment terms", "Authorized signatory"]:
            self.assertIn(value, document_text)
        second = self.client.post("/api/quotations", headers=self.staff_headers, json=payload).json()
        self.assertEqual(second["number"], "HW-2026-01002")
        current = self.settings()
        self.assertEqual(current["quotation"]["nextNumber"], 1003)
        self.assertEqual(self.client.post("/api/quotations", headers=self.staff_headers, json={**payload, "items": []}).status_code, 422)
        self.assertEqual(self.settings()["quotation"]["nextNumber"], 1003)
        self.assertEqual(self.client.put(f"/api/quotations/{quote['id']}", headers=self.staff_headers, json={"expectedVersion": 1, "status": "Sent"}).status_code, 403)
        self.assertEqual(self.client.put(f"/api/quotations/{quote['id']}", headers=self.owner_headers, json={"expectedVersion": 1, "status": "Sent"}).status_code, 200)
        self.save({"expectedSharedVersion": current["versions"]["shared"], "company": {"name": "New issuer"}})
        self.assertEqual(self.client.get(quote["versions"][0]["pdfPath"], headers=self.owner_headers).content, pdf)
