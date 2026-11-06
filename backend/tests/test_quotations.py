import hashlib
import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import Base, get_db
from app.main import app
from app.models.quotation import Quotation, QuotationFile
from auth_helpers import isolate_request_limits, authorize


class QuotationHttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.directory.name) / 'api.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        app.dependency_overrides[get_db] = lambda: self.db
        isolate_request_limits(self)
        self.client = TestClient(app)
        authorize(self.client, self.db)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()
        self.directory.cleanup()

    def document(self, **changes):
        return {"number": "NEM-001", "customer": "Example Engineering", "division": "nemilink",
                "contact": "Arun", "date": "2026-11-04", "validUntil": "2026-11-20", "tax": "18",
                "items": [{"description": "IoT controller", "quantity": "2", "rate": "100.05", "billing": "One-time"},
                          {"description": "Cloud monitoring", "quantity": "1", "rate": "50.00", "billing": "Monthly"}],
                "terms": "Payment within 15 days.\nWarranty as agreed.", **changes}

    def create(self, **changes):
        result = self.client.post("/api/quotations", json=self.document(**changes))
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    def pdf(self, quote):
        return self.client.get(f"/api/quotations/{quote['id']}/pdf").content

    def test_create_list_read_generated_pdf_and_status(self):
        quote = self.create()
        self.assertEqual(quote["totals"]["One-time"], {"subtotal": 200.1, "tax": 36.02, "total": 236.12})
        self.assertEqual(quote["totals"]["Monthly"]["total"], 59)
        self.assertEqual(len(self.client.get("/api/quotations").json()), 1)
        self.assertEqual(self.client.get(f"/api/quotations/{quote['id']}").json()["number"], "NEM-001")
        pdf = self.client.get(quote["versions"][0]["pdfPath"])
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertIn("inline", pdf.headers["content-disposition"])
        self.assertEqual(hashlib.sha256(pdf.content).hexdigest(), quote["versions"][0]["sha256"])
        text = " ".join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        for expected in ["IoT controller", "Cloud monitoring", "236.12", "recurring", "Warranty"]:
            self.assertIn(expected, text)
        updated = self.client.put(f"/api/quotations/{quote['id']}", json={"status": "Sent", "expectedVersion": 1})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["version"], 2)
        self.assertEqual(len(updated.json()["versions"]), 1)
        self.assertEqual(self.pdf(quote), pdf.content)
        self.assertIn("attachment", self.client.get(f"/api/quotations/{quote['id']}/pdf?download=true").headers["content-disposition"])

    def test_edit_retains_old_pdf_snapshot_and_rejects_stale_updates(self):
        original = self.create(status="Sent")
        old_file = self.pdf(original)
        edited = self.client.put(f"/api/quotations/{original['id']}", json={"expectedVersion": 1,
            "document": self.document(customer="Updated Company", tax="0")})
        self.assertEqual(edited.status_code, 200, edited.text)
        edited = edited.json()
        self.assertEqual(edited["status"], "Draft")
        self.assertEqual(len(edited["versions"]), 2)
        self.assertEqual(edited["versions"][0]["snapshot"]["customer"], "Example Engineering")
        self.assertEqual(self.client.get(original["versions"][0]["pdfPath"]).content, old_file)
        self.assertNotEqual(self.pdf(edited), old_file)
        stale = self.client.put(f"/api/quotations/{original['id']}", json={"expectedVersion": 1, "status": "Accepted"})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get(f"/api/quotations/{original['id']}").json()["status"], "Draft")

    def test_upload_and_revisions_keep_old_files_and_update_imported_metadata(self):
        pdf = self.pdf(self.create())
        metadata = self.document(number="EXT-1", items=[], amount="1500.50", tax="0", billing="Yearly")
        result = self.client.post("/api/quotations/upload", data={"metadata": json.dumps(metadata)},
                                  files={"file": ("../../original.pdf", pdf, "application/pdf")})
        self.assertEqual(result.status_code, 201, result.text)
        quote = result.json()
        self.assertEqual(quote["source"], "Uploaded")
        self.assertEqual(quote["versions"][0]["name"], "original.pdf")
        self.assertEqual(quote["totals"]["Yearly"]["total"], 1500.5)
        updated_meta = {**metadata, "amount": "2000.00", "validUntil": "2026-12-20"}
        revised = self.client.post(f"/api/quotations/{quote['id']}/revisions",
            data={"expectedVersion": "1", "metadata": json.dumps(updated_meta)}, files={"file": ("revision.pdf", pdf, "application/pdf")})
        self.assertEqual(revised.status_code, 201, revised.text)
        self.assertEqual(revised.json()["totals"]["Yearly"]["total"], 2000)
        self.assertEqual(revised.json()["versions"][0]["snapshot"]["amount"], "1500.50")
        stale = self.client.post(f"/api/quotations/{quote['id']}/revisions", data={"expectedVersion": "1"}, files={"file": ("x.pdf", pdf)})
        self.assertEqual(stale.status_code, 409)
        forbidden = self.client.put(f"/api/quotations/{quote['id']}", json={"expectedVersion": 2, "document": self.document()})
        self.assertEqual(forbidden.status_code, 409)

    def test_file_only_revision_preserves_details_and_resets_status(self):
        quote = self.create(status="Accepted")
        revised = self.client.post(f"/api/quotations/{quote['id']}/revisions", data={"expectedVersion": 1},
            files={"file": ("new.pdf", self.pdf(quote), "application/pdf")})
        self.assertEqual(revised.status_code, 201, revised.text)
        self.assertEqual(revised.json()["status"], "Draft")
        self.assertEqual(revised.json()["totals"], quote["totals"])
        self.assertEqual([item["revision"] for item in revised.json()["versions"]], [1, 2])

    def test_duplicate_number_is_case_insensitive_and_scoped_to_division(self):
        self.create()
        self.assertEqual(self.client.post("/api/quotations", json=self.document(number="nem-001")).status_code, 409)
        other = self.create(division="MMC")
        self.assertEqual(other["division"], "MMC")

    def test_archive_retains_files_and_enforces_version(self):
        quote = self.create()
        path = f"/api/quotations/{quote['id']}"
        self.assertEqual(self.client.delete(path + "?expectedVersion=4").status_code, 409)
        self.assertEqual(self.client.delete(path + "?expectedVersion=1").status_code, 204)
        self.assertEqual(self.client.get("/api/quotations").json(), [])
        for url in [path, path + "/pdf", quote["versions"][0]["pdfPath"]]:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(QuotationFile)), 1)
        self.assertEqual(self.client.post("/api/quotations", json=self.document()).status_code, 409)

    def test_invalid_documents_are_rejected_before_persistence(self):
        for changes in [{"items": []}, {"tax": "NaN"}, {"tax": "101"}, {"validUntil": "2026-01-01"},
                        {"division": "Unknown"}, {"customer": " "}, {"totals": {"One-time": {"total": 1}}},
                        {"items": [{"description": "Item", "quantity": "0", "rate": "5"}]}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/api/quotations", json=self.document(**changes)).status_code, 422)
        self.assertEqual(self.client.get("/api/quotations").json(), [])

    def test_invalid_password_and_oversized_uploads_do_not_save_records(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("password")
        encrypted = BytesIO()
        writer.write(encrypted)
        metadata = self.document(items=[], tax="0", amount="10")
        for content in [b"fake", b"%PDF-fake", encrypted.getvalue(), b"%PDF-" + b"x" * (10 * 1024 * 1024)]:
            result = self.client.post("/api/quotations/upload", data={"metadata": json.dumps(metadata)}, files={"file": ("x.pdf", content)})
            self.assertIn(result.status_code, [413, 422], result.text)
        self.assertEqual(self.client.get("/api/quotations").json(), [])

    def test_cross_quotation_file_and_missing_record_return_404(self):
        a, b = self.create(), self.create(number="NEM-002")
        self.assertEqual(self.client.get(f"/api/quotations/{b['id']}/versions/{a['versions'][0]['id']}/pdf").status_code, 404)
        self.assertEqual(self.client.get("/api/quotations/missing").status_code, 404)

    def test_failed_commit_rolls_back_metadata_and_binary_together(self):
        with patch.object(self.db, "commit", side_effect=SQLAlchemyError("simulated")):
            result = self.client.post("/api/quotations", json=self.document())
        self.assertEqual(result.status_code, 503)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Quotation)), 0)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(QuotationFile)), 0)

    def test_conflicting_edit_rolls_back_pdf_revision_and_version(self):
        self.create(number="EXISTING-1")
        original = self.create(status="Sent")
        conflict = self.client.put(f"/api/quotations/{original['id']}", json={"expectedVersion": 1,
            "document": self.document(number="existing-1")})
        self.assertEqual(conflict.status_code, 409)
        retained = self.client.get(f"/api/quotations/{original['id']}").json()
        self.assertEqual(retained["number"], original["number"])
        self.assertEqual(retained["version"], 1)
        self.assertEqual(retained["status"], "Sent")
        self.assertEqual(len(retained["versions"]), 1)

    def test_subcent_line_rounding_is_decimal_and_unrepresentable_totals_are_rejected(self):
        quote = self.create(tax="0", items=[{"description": "Fractional service", "quantity": "0.335", "rate": "3", "billing": "Monthly"}])
        self.assertEqual(quote["totals"]["Monthly"]["total"], 1.01)
        oversized = self.document(number="BIG-1", items=[{"description": "Too large", "quantity": "999999", "rate": "999999999.99"}])
        self.assertEqual(self.client.post("/api/quotations", json=oversized).status_code, 422)

    def test_retained_quotation_blocks_customer_deletion_by_alias(self):
        customer = self.client.post("/api/customers", json={"name": "Renamed Company", "aliases": ["Example Engineering"],
            "divisions": ["nemilink"], "contacts": [{"phone": "1234567890"}]}).json()
        quote = self.create()
        self.client.delete(f"/api/quotations/{quote['id']}?expectedVersion=1")
        self.assertEqual(self.client.delete(f"/api/customers/{customer['id']}?expectedVersion={customer['version']}").status_code, 409)
