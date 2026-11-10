"""Check embedded PDF branding without depending on frontend source files."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader
from app.services.quotation_pdf import generate_pdf


def snapshot(show_logo=True):
    return {
        "number": "ENGEN-QA-LOGO-001", "customer": "Example Engineering",
        "contact": "Engineering team", "address": "Chennai, Tamil Nadu",
        "division": "nemilink", "date": "2026-11-06", "validUntil": "2026-11-21",
        "currency": "INR", "tax": 18,
        "issuer": {"name": "ENGEN", "address": "Company address", "email": "sales@example.test"},
        "presentation": {"showLogo": show_logo, "showSignature": False},
        "items": [{"description": "Embedded IoT controller development", "quantity": 2,
                   "rate": 2500, "billing": "One-time"}],
        "totals": {"One-time": {"subtotal": 5000, "tax": 900, "total": 5900}},
        "terms": "Payment within 15 days.\nScope and warranty as agreed.",
    }


def image_count(page):
    objects = page["/Resources"].get("/XObject", {})
    return sum(item.get_object().get("/Subtype") == "/Image" for item in objects.values())


class QuotationBrandingTests(unittest.TestCase):
    def test_generated_pdf_embeds_packaged_logo_on_every_page(self):
        document = snapshot()
        document["items"] *= 45
        document["totals"] = {"One-time": {"subtotal": 225000, "tax": 40500, "total": 265500}}
        reader = PdfReader(BytesIO(generate_pdf(document)))
        self.assertGreater(len(reader.pages), 1)
        self.assertTrue(all(image_count(page) > 0 for page in reader.pages))
        text = " ".join(page.extract_text() for page in reader.pages)
        for value in (document["number"], document["customer"], "265,500.00"):
            self.assertIn(value, text)

    def test_logo_disabled_preserves_company_text_and_no_image(self):
        reader = PdfReader(BytesIO(generate_pdf(snapshot(show_logo=False))))
        self.assertEqual(image_count(reader.pages[0]), 0)
        self.assertIn("ENGEN", reader.pages[0].extract_text())

    def test_missing_optional_asset_retains_readable_company_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.services.quotation_pdf.LOGO_PATH", Path(directory) / "missing-logo.png"):
                reader = PdfReader(BytesIO(generate_pdf(snapshot())))
        self.assertEqual(image_count(reader.pages[0]), 0)
        self.assertIn("ENGEN", reader.pages[0].extract_text())
