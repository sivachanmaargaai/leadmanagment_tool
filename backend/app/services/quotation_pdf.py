"""Generate PDFs from validated, server-calculated quotation snapshots."""
from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "engen-logo.png"
FONT = "Helvetica"
BOLD = "Helvetica-Bold"
if Path("C:/Windows/Fonts/arial.ttf").is_file():
    pdfmetrics.registerFont(TTFont("CRMArial", "C:/Windows/Fonts/arial.ttf"))
    pdfmetrics.registerFont(TTFont("CRMArialBold", "C:/Windows/Fonts/arialbd.ttf"))
    FONT, BOLD = "CRMArial", "CRMArialBold"


def generate_pdf(snapshot):
    issuer = snapshot.get("issuer", {"name": "ENGEN"})
    presentation = snapshot.get("presentation", {"showLogo": True, "showSignature": False})
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=(595.28, 841.89), leftMargin=40, rightMargin=40,
                            topMargin=115, bottomMargin=48, title=snapshot["number"], author=issuer["name"])
    normal = ParagraphStyle("body", fontName=FONT, fontSize=9, leading=13, textColor=colors.HexColor("#172b35"), splitLongWords=True)
    heading = ParagraphStyle("heading", parent=normal, fontName=BOLD, fontSize=12, leading=17, spaceAfter=9)
    right = ParagraphStyle("right", parent=normal, alignment=TA_RIGHT)

    def paragraph(text, style=normal):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    def fitted(text, font, size, width):
        value = str(text)
        if pdfmetrics.stringWidth(value, font, size) <= width:
            return value
        while value and pdfmetrics.stringWidth(value + "...", font, size) > width:
            value = value[:-1]
        return value + "..."

    def draw_page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#075854"))
        canvas.rect(0, 829, 595.28, 13, fill=1, stroke=0)
        logo = LOGO_PATH
        if presentation.get("showLogo") and logo.is_file():
            canvas.drawImage(ImageReader(str(logo)), 40, 746, width=140, height=73, preserveAspectRatio=True, mask="auto")
        else:
            canvas.setFont(BOLD, 13)
            canvas.drawString(40, 772, fitted(issuer["name"], BOLD, 13, 265))
        canvas.setFont(BOLD, 19)
        canvas.drawRightString(555, 785, "QUOTATION")
        canvas.setFont(FONT, 10)
        canvas.drawRightString(555, 765, snapshot["division"])
        canvas.setStrokeColor(colors.HexColor("#dbe6e3"))
        canvas.line(40, 737, 555, 737)
        canvas.line(40, 38, 555, 38)
        canvas.setFont(FONT, 8)
        canvas.drawString(40, 25, fitted(issuer["name"] + " | " + snapshot["number"], FONT, 8, 420))
        canvas.drawRightString(555, 25, f"Page {document.page}")
        canvas.restoreState()

    story = [paragraph(snapshot["number"], heading)]
    issuer_details = [issuer.get("address", ""), " | ".join(value for value in [issuer.get("email"), issuer.get("phone"), issuer.get("website")] if value),
                      f"GST: {issuer['gst']}" if issuer.get("gst") else ""]
    for line in issuer_details:
        if line:
            story.append(paragraph(line))
    if any(issuer_details):
        story.append(Spacer(1, 12))
    info = [[paragraph("CUSTOMER", heading), paragraph("QUOTATION DETAILS", heading)],
            [paragraph(snapshot["customer"]), paragraph(f"Date: {snapshot['date']}")],
            [paragraph(snapshot.get("contact", "")), paragraph(f"Valid until: {snapshot['validUntil']}")],
            [paragraph(snapshot.get("address", "")), paragraph(f"Currency: {snapshot['currency']}")]]
    metadata = Table(info, colWidths=[300, 215], hAlign="LEFT")
    metadata.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [metadata, Spacer(1, 20)]
    rows = [[paragraph(label) for label in ["Description", "Billing", "Qty", "Rate", "Amount"]]]
    for item in snapshot["items"]:
        amount = (Decimal(str(item["quantity"])) * Decimal(str(item["rate"]))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rows.append([paragraph(item["description"]), paragraph(item["billing"]), paragraph(item["quantity"], right),
                     paragraph(f"{Decimal(str(item['rate'])):,.2f}", right), paragraph(f"{amount:,.2f}", right)])
    table = Table(rows, colWidths=[225, 70, 45, 80, 95], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f3ee")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe6e3"))]))
    story += [table, Spacer(1, 18), paragraph("Totals by billing period", heading)]
    for billing, total in snapshot["totals"].items():
        story += [paragraph(f"{billing} - Subtotal: {snapshot['currency']} {total['subtotal']:,.2f} | Tax ({snapshot['tax']}%): {total['tax']:,.2f}"),
                  paragraph(f"Total: {snapshot['currency']} {total['total']:,.2f}", heading), Spacer(1, 6)]
    if any(item["billing"] != "One-time" for item in snapshot["items"]):
        story += [paragraph("Monthly and yearly amounts are recurring charges for their respective billing periods."), Spacer(1, 12)]
    if snapshot.get("terms"):
        story += [paragraph("Terms & conditions", heading)]
        # Separate paragraphs keep long terms safely splittable across pages.
        story += [paragraph(line or " ") for line in snapshot["terms"].splitlines()]
    if presentation.get("showSignature"):
        story += [Spacer(1, 25), paragraph(f"For {issuer['name']}"), Spacer(1, 25), paragraph("Authorized signatory")]
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return output.getvalue()
