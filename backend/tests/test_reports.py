import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base, get_db
from app.main import app
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.models.quotation import Quotation
from auth_helpers import isolate_request_limits, authorize

NOW = datetime(2026, 11, 4, 6, tzinfo=timezone.utc)


class ReportScenarioTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'reports.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app)
        authorize(self.client, self.db)
        self.clock = patch("app.routers.reports.datetime")
        self.clock.start().now.return_value = NOW

    def tearDown(self):
        self.clock.stop()
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def seed(self):
        created = ["2026-10-31T18:29:59+00:00", "2026-10-31T18:30:00+00:00", "2026-11-01T12:00:00+00:00", "2026-11-05T00:00:00+00:00", "2026-11-06T00:00:00+00:00"]
        for i in range(5):
            self.db.add(Lead(id=f"L{i}", customer=f"Customer {i}" if i < 4 else "[QA TEST] Company",
                division=["MMC", "nemilink", "nemilink", "ClearCode Labs", "MMC"][i], description="Embedded IoT",
                status=["New", "Won", "Lost", "In Progress", "Follow-up"][i], priority=["High", "High", "Low", "Medium", "Medium"][i],
                lead_source=["Website", "Referral", "Known Network", "Phone", "Website"][i],
                referred_by={"name": "Ramesh", "email": "ref@example.test", "company": "Network"} if i in [1, 2] else None,
                created_at=datetime.fromisoformat(created[i])))
        self.db.flush()
        for i in range(5):
            billing = ["One-time", "Monthly", "Yearly", "One-time", "One-time"][i]
            amount = [118, 59, 200, 40, 99][i]
            self.db.add(Quotation(id=f"Q{i}", number=f"QUOTE-{i}" if i < 4 else "QA-DEMO-005", number_key=f"quote-{i}",
                customer=f"Customer {i}" if i < 4 else "[QA TEST] Company", division=["MMC", "nemilink", "nemilink", "ClearCode Labs", "MMC"][i],
                status="Sent" if i == 3 else "Accepted", source="Created",
                document={"date": "2026-11-01", "validUntil": "2026-11-03" if i == 3 else "2026-11-20",
                          "currency": ["INR", "INR", "USD", "INR", "EUR"][i],
                          "totals": {billing: {"subtotal": amount, "tax": 0, "total": amount}}}))
            due = ["2026-11-03T00:00:00+00:00", "2026-11-05T00:00:00+00:00", "2026-11-03T00:00:00+00:00", "2026-11-03T18:30:00+00:00", "2026-11-10T00:00:00+00:00"][i]
            self.db.add(FollowUp(id=f"F{i}", lead_id=f"L{i}", purpose=f"Task {i}", due_at=datetime.fromisoformat(due),
                assigned_to="Admin" if i in [0, 3] else "Priya", status="Completed" if i == 2 else "Pending"))
        self.db.add(Quotation(id="ARCHIVED", number="ARCHIVED", number_key="archived", customer="Customer 0", division="MMC",
            status="Accepted", source="Created", document={"date": "2026-11-01", "validUntil": "2026-11-20", "currency": "INR",
                "totals": {"One-time": {"subtotal": 999, "tax": 0, "total": 999}}}, deleted_at=NOW))
        self.db.add(FollowUp(id="ARCHIVED", lead_id="L0", purpose="Archived task", due_at=NOW, deleted_at=NOW))
        self.db.commit()

    def get(self, path, **params):
        result = self.client.get("/api/reports/" + path, params=params)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_01_empty_reports_and_zero_conversion(self):
        summary = self.get("summary")
        self.assertEqual(summary["totals"]["totalLeads"], 0)
        self.assertEqual(summary["totals"]["conversionRate"], 0)
        self.assertEqual(summary["acceptedValue"], [])
        for kind in ["leads", "sales", "follow-ups"]:
            self.assertEqual(self.get(kind)["rows"], [])

    def test_02_leads_conversion_sources_division_and_ist_boundaries(self):
        self.seed()
        summary = self.get("summary")
        self.assertEqual(summary["totals"]["totalLeads"], 4)
        self.assertEqual(summary["totals"]["conversionRate"], 50)
        report = self.get("leads", startDate="2026-11-01", endDate="2026-11-01", division="nemilink")
        self.assertEqual({x["id"] for x in report["rows"]}, {"L1", "L2"})
        self.assertEqual(len(report["referrals"]), 2)
        self.assertEqual(report["byDivision"][0]["conversionRate"], 50)
        self.assertEqual({x["name"] for x in report["bySource"]}, {"Referral", "Known Network"})
        self.assertEqual(len(self.get("leads", status="Won")["rows"]), 1)
        self.assertEqual(self.get("leads", startDate="2026-10-31", endDate="2026-10-31")["rows"][0]["id"], "L0")

    def test_03_quotations_separate_currencies_periods_expiry_and_archives(self):
        self.seed()
        report = self.get("sales")
        self.assertEqual(len(report["rows"]), 4)
        self.assertEqual(len(report["acceptedValue"]), 3)
        values = {(x["currency"], x["billing"]): x["total"] for x in report["acceptedValue"]}
        self.assertEqual(values, {("INR", "One-time"): 118, ("INR", "Monthly"): 59, ("USD", "Yearly"): 200})
        self.assertEqual(self.get("sales", status="Expired")["rows"][0]["id"], "Q3")
        self.assertEqual(self.get("sales", status="Sent")["rows"], [])
        self.assertEqual(self.get("sales", startDate="2026-11-02")["rows"], [])
        self.assertEqual(self.get("summary")["acceptedValue"], report["acceptedValue"])

    def test_04_followups_due_dates_staff_and_completion_exclusions(self):
        self.seed()
        report = self.get("follow-ups")
        self.assertEqual(report["summary"], {"total": 4, "pending": 3, "completed": 1, "overdue": 2})
        admin = next(x for x in report["byStaff"] if x["name"] == "Admin")
        self.assertEqual(admin["overdue"], 2)
        self.assertFalse(next(x for x in report["rows"] if x["id"] == "F2")["overdue"])
        scoped = self.get("follow-ups", startDate="2026-11-04", endDate="2026-11-04")
        self.assertEqual([x["id"] for x in scoped["rows"]], ["F3"])
        self.assertEqual(len(self.get("follow-ups", status="Completed")["rows"]), 1)

    def test_05_test_data_toggle_and_invalid_filters(self):
        self.seed()
        self.assertEqual(self.get("summary", includeTestData="true")["totals"]["totalLeads"], 5)
        for kind in ["leads", "sales", "follow-ups"]:
            self.assertEqual(len(self.get(kind, includeTestData="true")["rows"]), 5)
        for kind, params in [("summary", {"startDate": "2026-11-20", "endDate": "2026-11-01"}),
                             ("leads", {"division": "Unknown"}), ("sales", {"status": "Won"}),
                             ("follow-ups", {"status": "Sent"}), ("summary", {"startDate": "not-a-date"})]:
            with self.subTest(kind=kind, params=params):
                self.assertEqual(self.client.get("/api/reports/" + kind, params=params).status_code, 422)
