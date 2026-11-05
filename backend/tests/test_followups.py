import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.models.follow_up import FollowUp
from app.routers import followups as router
from app.routers.leads import create_lead, delete_lead
from app.schemas.follow_up import FollowUpCreate, FollowUpUpdate
from app.schemas.lead import LeadCreate


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.lead = create_lead(LeadCreate(customer="IoT customer", division="MMC", description="IoT prototype",
            leadSource="Known Network", referredBy={"id": "ref", "name": "Ramesh"}), self.db)
        self.now = datetime(2026, 11, 4, 10, tzinfo=timezone.utc)
        self.clock = patch("app.routers.followups.utc_now", return_value=self.now)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.db.close()
        self.engine.dispose()

    def create(self, **updates):
        data = {"leadId": self.lead.id, "purpose": "Quotation discussion", "dueAt": self.now + timedelta(hours=2), **updates}
        return router.create_follow_up(FollowUpCreate.model_validate(data), self.db)

    def error(self, status, function, *args):
        with self.assertRaises(HTTPException) as caught:
            function(*args)
        self.assertEqual(caught.exception.status_code, status)

    def test_create_list_get_reference_and_utc_serialization(self):
        item = self.create(dueAt="2026-11-04T18:00:00+05:30")
        payload = item.model_dump(by_alias=True)
        self.assertEqual(payload["customer"], "IoT customer")
        self.assertEqual(payload["referredBy"]["name"], "Ramesh")
        self.assertEqual(payload["dueAt"], datetime(2026, 11, 4, 12, 30, tzinfo=timezone.utc))
        self.assertEqual(len(router.get_follow_ups(self.db)), 1)
        self.assertEqual(router.get_follow_up(item.id, self.db).id, item.id)
        self.assertEqual(item.version, 1)

    def test_upcoming_and_overdue_boundaries_exclude_completed(self):
        past = self.create(dueAt=self.now - timedelta(minutes=1))
        boundary = self.create(dueAt=self.now)
        future = self.create()
        self.assertEqual([item.id for item in router.overdue_follow_ups(self.db)], [past.id])
        self.assertEqual({item.id for item in router.upcoming_follow_ups(self.db)}, {boundary.id, future.id})
        router.update_follow_up(past.id, FollowUpUpdate(status="Completed", outcome="Connected", completionNotes="Discussed"), self.db)
        self.assertEqual(router.overdue_follow_ups(self.db), [])

    def test_reschedule_retains_server_history_and_version(self):
        item = self.create()
        due = self.now + timedelta(days=1)
        self.error(422, router.update_follow_up, item.id, FollowUpUpdate(dueAt=due), self.db)
        result = router.update_follow_up(item.id, FollowUpUpdate(dueAt=due, rescheduleReason="Customer requested", expectedVersion=1), self.db)
        self.assertEqual(result.record.version, 2)
        self.assertEqual(len(result.record.history), 2)
        self.assertIn("Customer requested", result.record.history[-1]["message"])
        self.error(409, router.update_follow_up, item.id, FollowUpUpdate(notes="Stale", expectedVersion=1), self.db)

    def test_complete_and_next_task_are_saved_together(self):
        item = self.create()
        result = router.update_follow_up(item.id, FollowUpUpdate(status="Completed", outcome="Requested callback",
            completionNotes="Send the design brief", nextDueAt=self.now + timedelta(days=1), expectedVersion=1), self.db)
        self.assertEqual(result.record.status, "Completed")
        self.assertEqual(result.next_follow_up.status, "Pending")
        self.assertEqual(result.next_follow_up.lead_id, self.lead.id)
        self.assertEqual(len(router.get_follow_ups(self.db)), 2)
        self.db.refresh(self.lead)
        self.assertEqual(self.lead.status, "New")
        self.error(409, router.update_follow_up, item.id, FollowUpUpdate(status="Completed", outcome="Connected", completionNotes="Retry"), self.db)

    def test_invalid_next_date_leaves_original_pending(self):
        item = self.create()
        self.error(422, router.update_follow_up, item.id, FollowUpUpdate(status="Completed", outcome="Connected",
            completionNotes="Notes", nextDueAt=self.now - timedelta(minutes=1)), self.db)
        self.assertEqual(router.get_follow_up(item.id, self.db).status, "Pending")
        self.assertEqual(len(router.get_follow_ups(self.db)), 1)

    def test_completion_requires_notes_and_outcome(self):
        item = self.create()
        self.error(422, router.update_follow_up, item.id, FollowUpUpdate(status="Completed"), self.db)
        self.assertEqual(router.get_follow_up(item.id, self.db).status, "Pending")

    def test_delete_archives_and_preserves_foreign_key_history(self):
        item = self.create()
        router.delete_follow_up(item.id, self.db)
        self.assertEqual(router.get_follow_ups(self.db), [])
        self.error(404, router.get_follow_up, item.id, self.db)
        archived = self.db.get(FollowUp, item.id)
        self.assertIsNotNone(archived.deleted_at)
        self.assertIn("archived", archived.history[-1]["message"])
        self.error(409, delete_lead, self.lead.id, self.db)

    def test_missing_lead_and_invalid_fields(self):
        self.error(404, router.create_follow_up, FollowUpCreate(leadId="missing", purpose="Call", dueAt=self.now), self.db)
        for changes in [{"purpose": " "}, {"dueAt": "2026-11-04T18:00"}, {"reminderMinutes": -1}, {"type": "Invalid"}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                FollowUpCreate.model_validate({"leadId": self.lead.id, "purpose": "Call", "dueAt": self.now, **changes})
        with self.assertRaises(ValidationError):
            FollowUpUpdate(dueAt=None)
