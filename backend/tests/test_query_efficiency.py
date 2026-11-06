import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import event, func, select
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.services.settings import settings_response
from app.services.pagination import collection_query
from app.schemas.pagination import FollowUpList
from app.routers.workspace import metrics
import test_crm_access as fixtures


class QueryEfficiencyTests(unittest.TestCase):
    setUp = fixtures.CrmAccessTests.setUp
    tearDown = fixtures.CrmAccessTests.tearDown

    def test_empty_metrics_and_settings_use_bounded_queries(self):
        user = self.accounts[0]
        self.db.refresh(user)
        self.db.info["crm_actor"] = user
        statements = []
        def record(*args):
            statements.append(1)
        event.listen(self.engine, "before_cursor_execute", record)
        try:
            data = metrics(self.db)
            self.assertEqual(len(statements), 4)
            self.assertEqual(data["leads"]["total"], 0)
            self.assertEqual(data["followUps"], {"All": 0, "Today": 0, "Overdue": 0, "Upcoming": 0, "Completed": 0})
            statements.clear()
            saved = settings_response(self.db, user)
            self.assertEqual(len(statements), 1)
            self.assertEqual(saved["profile"]["name"], user.name)
            self.assertEqual(saved["versions"]["personal"], 0)
        finally:
            event.remove(self.engine, "before_cursor_execute", record)
            self.db.info.pop("crm_actor", None)

    def test_grouped_metrics_match_register_views_at_ist_midnight_and_staff_scope(self):
        at = datetime(2026, 11, 6, 6, 0, tzinfo=timezone.utc)
        start = datetime(2026, 11, 5, 18, 30, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        own = Lead(customer="Visible", division="MMC", description="Firmware", priority="High", assignee_user_id=self.accounts[2].id)
        hidden = Lead(customer="Hidden", division="MMC", description="Firmware", assignee_user_id=self.accounts[3].id)
        self.db.add_all([own, hidden]); self.db.flush()
        for due, status in [(start - timedelta(seconds=1), "Pending"), (start, "Pending"), (end - timedelta(seconds=1), "Pending"), (end, "Pending"), (at, "Completed")]:
            self.db.add(FollowUp(lead_id=own.id, purpose="Boundary", due_at=due, status=status))
        self.db.add(FollowUp(lead_id=hidden.id, purpose="Hidden", due_at=at))
        self.db.commit()
        self.db.info["crm_actor"] = self.accounts[2]
        try:
            with patch("app.routers.workspace.datetime", wraps=datetime) as clock:
                clock.now.return_value = at
                summary = metrics(self.db, division="MMC")
            self.assertEqual(summary["leads"]["total"], 1)
            self.assertEqual(summary["leads"]["high"], 1)
            self.assertEqual(summary["followUps"], {"All": 5, "Today": 2, "Overdue": 2, "Upcoming": 1, "Completed": 1})
            for view, total in summary["followUps"].items():
                query = collection_query(self.db, FollowUp, FollowUpList(view=view, division="MMC"), at)
                actual = self.db.scalar(select(func.count()).select_from(query.subquery()))
                self.assertEqual(actual, total, view)
        finally:
            self.db.info.pop("crm_actor", None)
