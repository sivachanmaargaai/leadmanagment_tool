from typing import Annotated
from app.schemas.pagination import QuotationList
from app.services.customer_links import validate_link
from app.services.pagination import collection_query, paginate
import hashlib
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, Query
from pydantic import ValidationError
from pypdf import PdfReader
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session, load_only

from app.services.crm_access import get_crm_db, scoped, require_admin, creation_assignment
from app.db.operations import database_operation
from app.models.quotation import Quotation, QuotationFile
from app.schemas.common import error_details
from app.schemas.quotation import QuotationDocument, QuotationUpdate, totals
from app.services.quotation_pdf import generate_pdf
from app.core.security import get_current_user, require_quotation_user
from app.models.user import User
from app.services.settings import enforce_quote_approval, quote_defaults, quote_presentation, shared_settings

router = APIRouter(prefix="/api/quotations", tags=["Quotations"], dependencies=[Depends(require_quotation_user)])
MAX_PDF_SIZE = 10 * 1024 * 1024


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def find(db, quotation_id):
    item = db.scalar(scoped(db, select(Quotation), Quotation).where(Quotation.id == quotation_id, Quotation.deleted_at.is_(None)).with_for_update().execution_options(populate_existing=True))
    if item is None:
        raise HTTPException(404, "Quotation not found")
    return item


def snapshot(data, uploaded=False):
    if uploaded and (data.items or data.tax != 0):
        raise HTTPException(422, "Uploaded PDFs require an inclusive amount, no line items, and zero additional tax")
    if not uploaded and not data.items:
        raise HTTPException(422, "Add at least one quotation item")
    result = data.model_dump(mode="json", by_alias=True)
    result["totals"] = totals(data, uploaded)
    return result


def response(item, db):
    files = db.scalars(select(QuotationFile).where(QuotationFile.quotation_id == item.id).order_by(QuotationFile.revision)).all()
    return {**item.document, "customerId": item.customer_id, "status": item.status, "id": item.id, "source": item.source, "version": item.version, "assigneeUserId": item.assignee_user_id,
            "createdAt": utc(item.created_at), "updatedAt": utc(item.updated_at),
            "versions": [{"id": f.id, "name": f.name, "revision": f.revision, "size": f.size, "sha256": f.sha256,
                          "uploadedAt": utc(f.uploaded_at), "snapshot": f.snapshot,
                          "pdfPath": f"/api/quotations/{item.id}/versions/{f.id}/pdf"} for f in files]}


def summaries(rows, db):
    if not rows:
        return []
    ids = [row.id for row in rows]
    latest = select(QuotationFile.quotation_id, func.max(QuotationFile.revision).label("revision"), func.count().label("count")).where(QuotationFile.quotation_id.in_(ids)).group_by(QuotationFile.quotation_id).subquery()
    files = {file.quotation_id: (file, count) for file, count in db.execute(select(QuotationFile, latest.c.count).options(load_only(QuotationFile.id, QuotationFile.quotation_id, QuotationFile.revision, QuotationFile.name)).join(latest, (QuotationFile.quotation_id == latest.c.quotation_id) & (QuotationFile.revision == latest.c.revision))).all()}
    result = []
    for row in rows:
        file, count = files.get(row.id, (None, 0))
        result.append({**{key: row.document.get(key) for key in ["number", "customer", "division", "date", "validUntil", "totals", "currency"]},
            "id": row.id, "customerId": row.customer_id, "status": row.status, "source": row.source, "version": row.version,
            "createdAt": utc(row.created_at), "updatedAt": utc(row.updated_at), "versionCount": count,
            "versions": [] if file is None else [{"id": file.id, "name": file.name, "revision": file.revision, "pdfPath": f"/api/quotations/{row.id}/versions/{file.id}/pdf"}]})
    return result


def add_file(db, item, content, name):
    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(413, "PDF must be 10 MB or smaller")
    # Original names are metadata only, never filesystem paths or HTTP headers.
    name = re.sub(r"[^A-Za-z0-9 ._()-]", "_", name.replace("\\", "/").split("/")[-1])[:176]
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    previous = db.scalar(select(QuotationFile.revision).where(QuotationFile.quotation_id == item.id)
                         .order_by(QuotationFile.revision.desc()).limit(1)) or 0
    db.add(QuotationFile(quotation_id=item.id, revision=previous + 1, name=name,
                        size=len(content), sha256=hashlib.sha256(content).hexdigest(), content=content,
                        snapshot={**item.document, "status": item.status}))


def save_new(db, data, document, content, source, filename):
    validate_link(db, data.customer_id, data.customer)
    item = Quotation(customer_id=data.customer_id, id=str(uuid.uuid4()), number=data.number, number_key=data.number.casefold(),
                     division=data.division, customer=data.customer, status=data.status,
                     source=source, document=document, assignee_user_id=creation_assignment(db))
    db.add(item)
    db.flush()
    add_file(db, item, content, filename)
    db.commit()
    return response(item, db)


def claim_version(db, item, expected_version):
    # Atomic compare-and-swap protects against simultaneous status, revision and edit requests.
    changed = db.execute(update(Quotation).where(Quotation.id == item.id,
        Quotation.version == expected_version, Quotation.deleted_at.is_(None)).values(
            version=Quotation.version + 1, updated_at=now()).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Quotation changed in another session. Reload and try again")
    db.refresh(item)


def parse_document(raw):
    try:
        return QuotationDocument.model_validate_json(raw)
    except ValidationError as error:
        raise HTTPException(422, error_details(error)) from None


async def read_pdf(file):
    content = await file.read(MAX_PDF_SIZE + 1)
    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(413, "PDF must be 10 MB or smaller")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(422, "Upload a valid PDF file")
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise ValueError("Encrypted or empty PDF")
    except Exception:
        raise HTTPException(422, "PDF is invalid, empty, or password protected") from None
    return content


@router.post("", status_code=201)
def create_quotation(data: QuotationDocument, db: Session = Depends(get_crm_db), actor: User = Depends(get_current_user)):
    with database_operation(db):
        data, settings = quote_defaults(db, data)
        enforce_quote_approval(data.status, settings, actor)
        document = quote_presentation(snapshot(data), settings)
        content = generate_pdf(document)
        return save_new(db, data, document, content, "Created", f"{data.number}.pdf")


@router.post("/upload", status_code=201)
async def upload_quotation(metadata: str = Form(max_length=200000), file: UploadFile = File(), db: Session = Depends(get_crm_db), actor: User = Depends(get_current_user)):
    data = parse_document(metadata)
    content = await read_pdf(file)
    with database_operation(db):
        data, settings = quote_defaults(db, data, uploaded=True)
        enforce_quote_approval(data.status, settings, actor)
        document = snapshot(data, uploaded=True)
        return save_new(db, data, document, content, "Uploaded", file.filename or "quotation.pdf")


@router.get("")
def get_quotations(db: Session = Depends(get_crm_db), filters: Annotated[QuotationList, Query()] = QuotationList()):
    with database_operation(db):
        return paginate(db, collection_query(db, Quotation, filters, now()), Quotation, filters, lambda item: response(item, db), render_many=(lambda rows: summaries(rows, db)) if filters.summary else None)


@router.get("/{quotation_id}")
def get_quotation(quotation_id: str, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return response(find(db, quotation_id), db)


@router.put("/{quotation_id}")
def update_quotation(quotation_id: str, data: QuotationUpdate, db: Session = Depends(get_crm_db), actor: User = Depends(get_current_user)):
    with database_operation(db):
        item = find(db, quotation_id)
        if data.document is not None:
            if item.source != "Created":
                raise HTTPException(409, "Upload a replacement PDF to revise an imported quotation")
            details_input = data.document
            if "customer_id" not in details_input.model_fields_set:
                details_input = details_input.model_copy(update={"customer_id": item.customer_id})
            details, settings = quote_defaults(db, details_input, existing_number=item.number)
            validate_link(db, details.customer_id, details.customer, item)
            document = quote_presentation(snapshot(details), settings)
            content = generate_pdf(document)
            claim_version(db, item, data.expected_version)
            item.document, item.number, item.number_key = document, details.number, details.number.casefold()
            item.customer_id = details.customer_id
            item.customer, item.division, item.status = details.customer, details.division, "Draft"
            # Changes to document details always create a retained PDF revision.
            add_file(db, item, content, f"{item.number}.pdf")
        else:
            settings, _ = shared_settings(db)
            enforce_quote_approval(data.status, settings, actor)
            claim_version(db, item, data.expected_version)
            item.status = data.status
        db.commit()
        return response(item, db)


@router.post("/{quotation_id}/revisions", status_code=201)
async def upload_revision(quotation_id: str, expected_version: int = Form(alias="expectedVersion", ge=1),
                          file: UploadFile = File(), metadata: str | None = Form(default=None, max_length=200000),
                          db: Session = Depends(get_crm_db)):
    content = await read_pdf(file)
    data = parse_document(metadata) if metadata is not None else None
    document = None
    with database_operation(db):
        item = find(db, quotation_id)
        if data is not None:
            if "customer_id" not in data.model_fields_set:
                data = data.model_copy(update={"customer_id": item.customer_id})
            data, _ = quote_defaults(db, data, uploaded=True)
            validate_link(db, data.customer_id, data.customer, item)
            document = snapshot(data, uploaded=True)
        # Revised imported amounts/dates may be supplied explicitly with the replacement PDF.
        if document is not None and item.source != "Uploaded":
            raise HTTPException(409, "Edit generated quotation details using the quotation editor")
        claim_version(db, item, expected_version)
        if document is not None:
            item.document, item.number, item.number_key = document, data.number, data.number.casefold()
            item.customer_id = data.customer_id
            item.customer, item.division = data.customer, data.division
        item.status = "Draft"
        add_file(db, item, content, file.filename or "revision.pdf")
        db.commit()
        return response(item, db)


def pdf_response(db, quotation_id, version_id=None, download=False):
    find(db, quotation_id)
    query = select(QuotationFile).where(QuotationFile.quotation_id == quotation_id)
    query = query.where(QuotationFile.id == version_id) if version_id else query.order_by(QuotationFile.revision.desc())
    file = db.scalar(query.limit(1))
    if file is None:
        raise HTTPException(404, "PDF revision not found")
    return Response(file.content, media_type="application/pdf", headers={
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{file.name}"',
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.get("/{quotation_id}/pdf")
def latest_pdf(quotation_id: str, download: bool = False, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return pdf_response(db, quotation_id, download=download)


@router.get("/{quotation_id}/versions/{version_id}/pdf")
def version_pdf(quotation_id: str, version_id: str, download: bool = False, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return pdf_response(db, quotation_id, version_id, download)


@router.delete("/{quotation_id}", status_code=204)
def delete_quotation(quotation_id: str, expectedVersion: int, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        require_admin(db)
        item = find(db, quotation_id)
        claim_version(db, item, expectedVersion)
        item.deleted_at = now()
        db.commit()
