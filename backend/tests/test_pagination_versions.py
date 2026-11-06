import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.models.lead import Lead
from app.models.customer import Customer
from app.models.follow_up import FollowUp
from app.models.quotation import Quotation
import test_crm_access as fixtures


class PaginationVersionTests(unittest.TestCase):
    setUp = fixtures.CrmAccessTests.setUp
    tearDown = fixtures.CrmAccessTests.tearDown
    lead = fixtures.CrmAccessTests.lead
    customer = fixtures.CrmAccessTests.customer
    quote = fixtures.CrmAccessTests.quote
    assign = fixtures.CrmAccessTests.assign

    def test_pages_are_bounded_stable_scoped_and_search_escapes_wildcards(self):
        at = datetime(2026, 11, 5, tzinfo=timezone.utc)
        for number in range(125):
            self.db.add(Lead(id=f"lead-{number:03}", customer=f"Customer {number:03}", division="MMC", description="Firmware", created_at=at,
                             assignee_user_id=self.accounts[2 if number < 70 else 3].id))
        self.db.add(Lead(customer="Literal 10%_done", division="nemilink", description="IoT", assignee_user_id=self.accounts[2].id))
        self.db.commit()
        first = self.client.get("/api/leads?paged=true&pageSize=25", headers=self.headers[2]).json()
        second = self.client.get("/api/leads?paged=true&pageSize=25&page=2", headers=self.headers[2]).json()
        self.assertEqual(first["total"], 71)
        self.assertEqual(first["pages"], 3)
        self.assertTrue(first["hasMore"])
        self.assertEqual(len(first["items"]), 25)
        self.assertFalse({x["id"] for x in first["items"]} & {x["id"] for x in second["items"]})
        self.assertEqual(first, self.client.get("/api/leads?paged=true&pageSize=25", headers=self.headers[2]).json())
        self.assertEqual(len(self.client.get("/api/leads").json()), 100)
        empty = self.client.get("/api/leads?paged=true&page=99&pageSize=25", headers=self.headers[2]).json()
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["total"], 71)
        literal = self.client.get("/api/leads", params={"paged": "true", "q": "%_"}, headers=self.headers[2]).json()
        self.assertEqual(literal["total"], 1)
        self.assertEqual(self.client.get("/api/leads?paged=true&q=Customer%20124", headers=self.headers[2]).json()["total"], 0)
        for query in ["page=0", "pageSize=101", "q=" + "x" * 121, "division=invalid", "status=invalid", "unknown=x"]:
            self.assertEqual(self.client.get("/api/leads?" + query).status_code, 422)

    def test_customer_contact_referral_search_and_module_filters(self):
        customer = self.customer()
        result = self.client.get("/api/customers", params={"paged": "true", "q": "123456", "division": "MMC", "type": "Company"}).json()
        self.assertEqual([item["id"] for item in result["items"]], [customer["id"]])
        self.assertEqual(self.client.get("/api/customers?paged=true&type=Individual").json()["total"], 0)
        self.assertEqual(self.client.get("/api/customers?paged=true", headers=self.headers[3]).json()["total"], 0)
        self.assertEqual(self.client.get("/api/customers?type=Unknown").status_code, 422)

    def test_followup_time_views_archive_filter_and_quote_expiry(self):
        lead = self.lead()
        self.assign("leads", lead)
        now = datetime.now(timezone.utc)
        for name, due in [("Late", now - timedelta(days=3)), ("Future", now + timedelta(days=3))]:
            self.db.add(FollowUp(lead_id=lead["id"], purpose=name, due_at=due))
        self.db.commit()
        future = self.client.get("/api/follow-ups?paged=true&view=Upcoming&q=Future", headers=self.headers[2]).json()
        self.assertEqual(future["total"], 1)
        late = self.client.get("/api/follow-ups/overdue?paged=true", headers=self.headers[2]).json()
        self.assertEqual(late["total"], 1)
        self.assertEqual(self.client.get("/api/follow-ups?paged=true", headers=self.headers[3]).json()["total"], 0)
        self.assertEqual(self.client.get("/api/follow-ups?date=invalid").status_code, 422)
        quote = self.quote()
        stored = self.db.get(Quotation, quote["id"])
        stored.status = "Sent"
        stored.document = {**stored.document, "validUntil": "2020-01-01"}
        self.db.commit()
        self.assertEqual(self.client.get("/api/quotations?paged=true&status=Expired&q=ACCESS").json()["total"], 1)
        self.assertEqual(self.client.get("/api/quotations?paged=true&status=Sent").json()["total"], 0)

    def test_lead_update_delete_preconditions_and_reassignment_invalidate_stale_edits(self):
        lead = self.lead()
        path = f"/api/leads/{lead['id']}"
        self.assertEqual(self.client.put(path, json={"priority": "High"}).status_code, 428)
        changed = self.client.put(path, json={"priority": "High", "expectedVersion": 1})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()["version"], 2)
        self.assertEqual(self.client.put(path, json={"status": "Won", "expectedVersion": 1}).status_code, 409)
        self.assertEqual(self.client.delete(path + "?expectedVersion=1").status_code, 409)
        self.assertEqual(self.client.delete(path).status_code, 428)
        current = changed.json()
        self.assertEqual(self.assign("leads", current).status_code, 200)
        self.assertEqual(self.client.put(path, headers=self.headers[2], json={"priority": "Low", "expectedVersion": 2}).status_code, 409)
        latest = self.client.get(path).json()
        self.assertEqual(latest["version"], 3)
        self.assertEqual(latest["status"], "New")
        self.assertEqual(latest["priority"], "High")

    def test_customer_stale_full_form_does_not_replace_contacts_history_or_profile(self):
        customer = self.customer()
        path = f"/api/customers/{customer['id']}"
        changed = self.client.put(path, json={"notes": "First editor", "expectedVersion": 1})
        self.assertEqual(changed.status_code, 200)
        stale = self.client.put(path, json={"contacts": [{"phone": "999"}], "history": [], "notes": "Overwrite", "expectedVersion": 1})
        self.assertEqual(stale.status_code, 409)
        saved = self.client.get(path).json()
        self.assertEqual(saved["notes"], "First editor")
        self.assertEqual(saved["contacts"][0]["phone"], "1234567890")
        self.assertEqual(self.client.delete(path + "?expectedVersion=1").status_code, 409)
        self.assertEqual(self.client.delete(path + "?expectedVersion=2").status_code, 204)

    def test_followup_requires_version_and_completion_cannot_duplicate_next_task(self):
        lead = self.lead()
        response = self.client.post("/api/follow-ups", json={"leadId": lead["id"], "purpose": "Discussion", "dueAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
        task = response.json()
        path = f"/api/follow-ups/{task['id']}"
        self.assertEqual(self.client.put(path, json={"notes": "No version"}).status_code, 428)
        payload = {"status": "Completed", "outcome": "Connected", "completionNotes": "Discussed", "nextDueAt": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), "expectedVersion": 1}
        self.assertEqual(self.client.put(path, json=payload).status_code, 200)
        self.assertEqual(self.client.put(path, json=payload).status_code, 409)
        self.assertEqual(len(self.client.get("/api/follow-ups").json()), 2)
        self.assertEqual(self.client.delete(path).status_code, 428)
        self.assertEqual(self.client.delete(path + "?expectedVersion=1").status_code, 409)

    def test_assignment_requires_both_version_and_previous_assignee(self):
        lead = self.lead()
        path = f"/api/access/assignments/leads/{lead['id']}"
        payload = {"assigneeUserId": self.accounts[2].id, "expectedAssigneeUserId": lead["assigneeUserId"]}
        self.assertEqual(self.client.put(path, json=payload).status_code, 428)
        self.assertEqual(self.client.put(path, json={**payload, "expectedVersion": 1}).status_code, 200)
        back = {"assigneeUserId": lead["assigneeUserId"], "expectedAssigneeUserId": self.accounts[2].id, "expectedVersion": 2}
        self.assertEqual(self.client.put(path, json=back).status_code, 200)
        self.assertEqual(self.client.put(path, json={**payload, "expectedVersion": 1}).status_code, 409)
        self.assertEqual(self.client.get("/api/access/assignments?q=NoMatch").json()["records"], [])
