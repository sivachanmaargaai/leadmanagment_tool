from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, MetaData, select
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.quotation import Quotation, QuotationFile
from app.models.follow_up import FollowUp
import test_crm_access as fixtures


class CustomerLinkTests(unittest.TestCase):
    setUp = fixtures.CrmAccessTests.setUp
    tearDown = fixtures.CrmAccessTests.tearDown
    lead = fixtures.CrmAccessTests.lead
    customer = fixtures.CrmAccessTests.customer
    quote = fixtures.CrmAccessTests.quote
    assign = fixtures.CrmAccessTests.assign

    def test_explicit_id_survives_rename_and_duplicate_names_do_not_merge(self):
        profile = self.customer()
        duplicate = self.customer()
        lead = self.client.post("/api/leads", json={"customer": profile["name"], "customerId": profile["id"], "division": "MMC", "description": "Firmware"}).json()
        self.assertEqual(lead["customerId"], profile["id"])
        changed = self.client.put(f"/api/customers/{profile['id']}", json={"name": "Renamed profile", "expectedVersion": profile["version"]})
        self.assertEqual(changed.status_code, 200)
        page = self.client.get("/api/leads", params={"customerId": profile["id"], "paged": True}).json()
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["items"][0]["customer"], "Embedded prospect")
        self.assertEqual(self.client.get("/api/leads", params={"customerId": duplicate["id"], "paged": True}).json()["total"], 0)
        self.assertEqual(self.client.delete(f"/api/customers/{profile['id']}?expectedVersion=2").status_code, 409)
        self.assertEqual(self.client.put(f"/api/leads/{lead['id']}", json={"customer": "Other", "expectedVersion": 1}).status_code, 422)
        synced = self.client.put(f"/api/leads/{lead['id']}", json={"customerId": profile["id"], "customer": "Renamed profile", "expectedVersion": 1})
        self.assertEqual(synced.status_code, 200)
        self.assertEqual(self.client.put(f"/api/leads/{lead['id']}", json={"customerId": None, "customer": "Other", "expectedVersion": 2}).status_code, 200)

    def test_profile_id_is_not_a_permission_grant(self):
        profile = self.customer()
        payload = {"customer": profile["name"], "customerId": profile["id"], "division": "MMC", "description": "Firmware"}
        self.assertEqual(self.client.post("/api/leads", json=payload, headers=self.headers[2]).status_code, 404)
        self.assertEqual(self.assign("customers", profile).status_code, 200)
        result = self.client.post("/api/leads", json=payload, headers=self.headers[2])
        self.assertEqual(result.status_code, 201, result.text)
        lead = result.json()
        self.assertEqual(self.client.get("/api/leads", params={"customerId": profile["id"], "paged": True}, headers=self.headers[3]).json()["total"], 0)
        reassigned = self.client.get(f"/api/customers/{profile['id']}").json()
        self.assertEqual(self.assign("customers", reassigned, target=3).status_code, 200)
        self.assertEqual(self.client.put(f"/api/leads/{lead['id']}", headers=self.headers[2], json={"priority": "High", "expectedVersion": 1}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/customers/{profile['id']}", headers=self.headers[2]).status_code, 404)

    def test_manual_link_is_admin_only_versioned_audited_and_keeps_pdf(self):
        quote, profile = self.quote(), self.customer()
        before = self.db.scalar(select(QuotationFile).where(QuotationFile.quotation_id == quote["id"]))
        original = (before.content, before.sha256, before.snapshot.copy())
        path = f"/api/customer-links/quotations/{quote['id']}"
        payload = {"customerId": profile["id"], "expectedVersion": quote["version"]}
        self.assertEqual(self.client.put(path, json=payload, headers=self.headers[2]).status_code, 403)
        self.assertEqual(self.client.put(path, json=payload).status_code, 200)
        self.assertEqual(self.client.put(path, json=payload).status_code, 409)
        full = self.client.get(f"/api/quotations/{quote['id']}").json()
        self.assertEqual(full["customerId"], profile["id"])
        self.db.expire_all()
        after = self.db.get(QuotationFile, before.id)
        self.assertEqual((after.content, after.sha256, after.snapshot), original)
        archived = self.client.delete(f"/api/quotations/{quote['id']}?expectedVersion={full['version']}")
        self.assertEqual(archived.status_code, 204)
        retained = self.db.get(Quotation, quote["id"]); self.db.refresh(retained)
        archived_version = retained.version
        self.assertEqual(self.client.put(path, json={"customerId": None, "expectedVersion": archived_version}).status_code, 200)
        self.assertEqual(self.client.put(path, json={"customerId": profile["id"], "expectedVersion": archived_version + 1}).status_code, 200)
        # Keep a second active document for the compact-list contract.
        self.client.post("/api/quotations", json={"number": "SUMMARY", "customer": "Other", "division": "MMC", "date": "2026-11-06", "items": [{"description": "QA", "quantity": 1, "rate": 100}]})
        summary = self.client.get("/api/quotations?paged=true&summary=true").json()["items"][0]
        self.assertEqual(summary["versionCount"], 1)
        self.assertNotIn("items", summary)
        self.assertNotIn("snapshot", summary["versions"][0])

    def test_large_overview_totals_are_exact_scoped_and_payload_bounded(self):
        profile = self.customer()
        at = datetime.now(timezone.utc)
        for index in range(130):
            lead = Lead(customer="Many", customer_id=profile["id"], division="MMC", description="Firmware", priority="High", status="Won" if index == 0 else "New", assignee_user_id=self.accounts[2].id)
            self.db.add(lead); self.db.flush()
            self.db.add(FollowUp(lead_id=lead.id, purpose="Task", due_at=at - timedelta(days=1), reminder_minutes=30))
        self.db.add(Lead(customer="Hidden", division="MMC", description="Hidden", assignee_user_id=self.accounts[3].id))
        self.db.commit()
        result = self.client.get("/api/workspace/overview", headers=self.headers[2])
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["metrics"]["leads"], {"total": 130, "active": 129, "high": 129, "won": 1, "pipeline": {"New": 129, "Won": 1}})
        self.assertEqual(data["metrics"]["followUps"]["Overdue"], 130)
        self.assertEqual([len(data[key]) for key in ["recentLeads", "queue", "alertLeads", "alertFollowUps"]], [5, 3, 20, 20])
        self.assertEqual(self.client.get("/api/workspace/overview", headers=self.headers[3]).json()["metrics"]["leads"]["total"], 1)
        row = self.client.get("/api/customers?paged=true").json()["items"][0]
        self.assertEqual((row["leadCount"], row["stage"]), (130, "Converted Customer"))

    def test_reminder_flags_are_applied_before_limit(self):
        lead = self.lead()
        at = datetime.now(timezone.utc)
        for index in range(25):
            self.db.add(FollowUp(lead_id=lead["id"], purpose="Old", due_at=at - timedelta(days=1)))
        self.db.add(FollowUp(lead_id=lead["id"], purpose="Due soon", due_at=at + timedelta(minutes=10), reminder_minutes=30))
        self.db.add(FollowUp(lead_id=lead["id"], purpose="Not eligible", due_at=at + timedelta(minutes=10), reminder_minutes=0))
        self.db.commit()
        data = self.client.get("/api/workspace/overview?overdue=false").json()
        self.assertEqual([row["purpose"] for row in data["alertFollowUps"]], ["Due soon"])
        self.assertEqual(self.client.get("/api/workspace/overview?overdue=false&followUp=false").json()["alertFollowUps"], [])

    def test_migration_links_only_unique_names_preserves_documents_and_downgrades(self):
        self.customer()
        lead, quote = self.lead(), self.quote()
        ambiguous = self.lead("Ambiguous")
        for index in range(2):
            self.db.add(Customer(name=f"Profile {index}", aliases=["Ambiguous"]))
        self.db.commit()
        path = Path(self.directory.name) / "migration.db"
        engine = create_engine(f"sqlite:///{path}")
        config = Config("alembic.ini")
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "20261105_0010")
            meta = MetaData(); meta.reflect(connection)
            for table in [Customer.__table__, Lead.__table__, Quotation.__table__, QuotationFile.__table__]:
                rows = self.db.execute(select(table)).mappings().all()
                for row in rows:
                    values = {key: value for key, value in row.items() if key in meta.tables[table.name].c}
                    connection.execute(meta.tables[table.name].insert().values(**values))
            command.upgrade(config, "head")
            meta = MetaData(); meta.reflect(connection)
            leads = meta.tables["leads"]
            self.assertIsNotNone(connection.scalar(select(leads.c.customer_id).where(leads.c.id == lead["id"])))
            self.assertIsNone(connection.scalar(select(leads.c.customer_id).where(leads.c.id == ambiguous["id"])))
            quotes = meta.tables["quotations"]
            stored = connection.execute(select(quotes).where(quotes.c.id == quote["id"])).mappings().one()
            original = self.db.get(Quotation, quote["id"])
            self.assertEqual(stored["document"], original.document)
            self.assertEqual(stored["version"], original.version + 1)
            command.downgrade(config, "20261105_0010")
        engine.dispose()
