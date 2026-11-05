import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import Base
from app.main import database_health
from app.routers import customers as customers
from app.routers import leads as leads
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.schemas.lead import LeadCreate, LeadResponse, LeadUpdate


class CrmHandlerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def lead(self, **updates):
        data = {"customer": "Example Engineering", "division": "MMC", "description": "IoT controller", **updates}
        return leads.create_lead(LeadCreate.model_validate(data), self.db)

    def customer(self, **updates):
        data = {"name": "Example Engineering", "divisions": ["MMC"],
                "contacts": [{"name": "Arun", "email": "arun@example.com"}], **updates}
        return customers.create_customer(CustomerCreate.model_validate(data), self.db)

    def assert_http_error(self, code, function, *args):
        with self.assertRaises(HTTPException) as caught:
            function(*args)
        self.assertEqual(caught.exception.status_code, code)

    def test_lead_crud_and_response_aliases(self):
        lead = self.lead()
        lid = lead.id
        self.assertEqual(len(leads.get_leads(self.db)), 1)
        self.assertEqual(leads.get_lead(lid, self.db).id, lid)
        leads.update_lead(lid, LeadUpdate(status="Won", priority="High"), self.db)
        self.db.expunge_all()
        payload = LeadResponse.model_validate(leads.get_lead(lid, self.db)).model_dump(by_alias=True)
        self.assertEqual(payload["status"], "Won")
        self.assertEqual(payload["leadSource"], "Direct Enquiry")
        self.assertIn("createdAt", payload)
        leads.delete_lead(lid, self.db)
        self.assert_http_error(404, leads.get_lead, lid, self.db)

    def test_customer_crud_persists_camelcase_fields(self):
        customer = self.customer(assignedTo="Priya", leadSource="Website")
        cid = customer.id
        self.assertEqual(len(customers.get_customers(self.db)), 1)
        self.assertEqual(customers.get_customer(cid, self.db).assigned_to, "Priya")
        customers.update_customer(cid, CustomerUpdate(assignedTo="Arun", leadSource="Phone", referenceNotes="Called"), self.db)
        self.db.expunge_all()
        payload = CustomerResponse.model_validate(customers.get_customer(cid, self.db)).model_dump(by_alias=True)
        self.assertEqual(payload["assignedTo"], "Arun")
        self.assertEqual(payload["leadSource"], "Phone")
        self.assertEqual(payload["referenceNotes"], "Called")
        self.assertIn("createdAt", payload)
        customers.delete_customer(cid, self.db)
        self.assert_http_error(404, customers.get_customer, cid, self.db)

    def test_invalid_lead_enums_whitespace_and_null_are_rejected(self):
        for changes in [{"customer": "  "}, {"status": "Wrong"}, {"priority": "Wrong"}, {"division": "Unknown"}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                LeadCreate.model_validate({"customer": "A", "description": "IoT", "division": "MMC", **changes})
        with self.assertRaises(ValidationError):
            LeadUpdate(customer=None)

    def test_invalid_customer_contact_division_and_readonly_fields(self):
        for data in [{"name": "A"}, {"name": "A", "divisions": ["MMC"], "contacts": [{"email": "bad"}]},
                     {"name": "A", "divisions": ["Unknown"], "contacts": [{"phone": "123"}]},
                     {"name": "A", "id": "client", "stage": "Prospect"}]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                CustomerCreate.model_validate(data)
        with self.assertRaises(ValidationError):
            CustomerUpdate(name=None)

    def test_merged_update_validates_contact_and_reference_requirements(self):
        customer = self.customer(leadSource="Known Network", referredBy={"id": "ref-1", "name": "Ramesh"})
        cid = customer.id
        self.assert_http_error(422, customers.update_customer, cid, CustomerUpdate(contacts=[]), self.db)
        self.assert_http_error(422, customers.update_customer, cid, CustomerUpdate(referredBy=None), self.db)
        updated = customers.update_customer(cid, CustomerUpdate(leadSource="Direct Enquiry", referredBy=None), self.db)
        self.assertIsNone(updated.referred_by)

    def test_lead_reference_requires_contact(self):
        with self.assertRaises(ValidationError):
            LeadCreate(customer="A", description="IoT", division="MMC", leadSource="Referral")
        lead = self.lead(leadSource="Referral", referredBy={"id": "ref-1", "name": "Ramesh"})
        self.assert_http_error(422, leads.update_lead, lead.id, LeadUpdate(referredBy=None), self.db)

    def test_deleting_linked_customer_is_blocked(self):
        customer = self.customer()
        self.lead()
        self.assert_http_error(409, customers.delete_customer, customer.id, self.db)
        self.assertEqual(customers.get_customer(customer.id, self.db).name, "Example Engineering")

    def test_missing_records_return_404(self):
        for read, update, delete, schema in [(leads.get_lead, leads.update_lead, leads.delete_lead, LeadUpdate),
                                             (customers.get_customer, customers.update_customer, customers.delete_customer, CustomerUpdate)]:
            self.assert_http_error(404, read, "missing", self.db)
            self.assert_http_error(404, update, "missing", schema(), self.db)
            self.assert_http_error(404, delete, "missing", self.db)

    def test_database_write_failure_rolls_back(self):
        session = MagicMock()
        session.get.return_value = None
        session.commit.side_effect = SQLAlchemyError("simulated failure")
        data = LeadCreate(customer="A", division="MMC", description="IoT")
        self.assert_http_error(503, leads.create_lead, data, session)
        session.rollback.assert_called_once()

    def test_database_health_returns_503_when_disconnected(self):
        with patch("app.main.engine.connect", side_effect=SQLAlchemyError("offline")):
            self.assert_http_error(503, database_health)


class MigrationTests(unittest.TestCase):
    def test_upgrade_matches_models_and_downgrade_is_reversible(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'migration.db'}")
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            try:
                with engine.begin() as connection:
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
                    self.assertTrue({"leads", "customers"}.issubset(inspect(connection).get_table_names()))
                    self.assertEqual(compare_metadata(MigrationContext.configure(connection), Base.metadata), [])
                    command.downgrade(config, "base")
                    self.assertNotIn("leads", inspect(connection).get_table_names())
                    self.assertNotIn("customers", inspect(connection).get_table_names())
                    self.assertNotIn("follow_ups", inspect(connection).get_table_names())
            finally:
                engine.dispose()
