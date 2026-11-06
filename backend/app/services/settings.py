from datetime import timedelta

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update, literal

from app.core.security import now
from app.models.settings import UserPreferences, WorkspaceSettings
from app.models.quotation import Quotation
from app.schemas.settings import PersonalData, SharedData
from app.schemas.common import error_details
from app.services.permissions import quotations_allowed


def shared_settings(db, lock=False):
    row = db.scalar(select(WorkspaceSettings).where(WorkspaceSettings.id == 1).with_for_update().execution_options(populate_existing=True)) if lock else db.get(WorkspaceSettings, 1)
    return SharedData.model_validate(row.data if row else {}), row


def personal_settings(db, user_id):
    row = db.get(UserPreferences, user_id)
    return PersonalData.model_validate(row.data if row else {}), row


def settings_response(db, user):
    anchor = select(literal(1).label("anchor")).subquery()
    shared_row, personal_row = db.execute(select(WorkspaceSettings, UserPreferences).select_from(anchor)
        .outerjoin(WorkspaceSettings, WorkspaceSettings.id == 1)
        .outerjoin(UserPreferences, UserPreferences.user_id == user.id)).one()
    shared = SharedData.model_validate(shared_row.data if shared_row else {})
    personal = PersonalData.model_validate(personal_row.data if personal_row else {})
    data = shared.model_dump(mode="json")
    data.update(profile={"name": user.name, "email": user.email, "phone": personal.phone, "designation": personal.designation},
                notifications=personal.notifications.model_dump(), workspace=personal.workspace.model_dump(),
                versions={"shared": shared_row.version if shared_row else 1, "personal": personal_row.version if personal_row else 0, "profile": user.version},
                canManageShared=user.is_owner, canAccessQuotations=quotations_allowed(user))
    if not data["canAccessQuotations"]:
        data.pop("quotation")
        data["notifications"]["quotationExpiry"] = False
    return data


def enforce_lead_requirements(payload, defaults, fields=None):
    fields = fields if fields is not None else {"contact", "description"}
    if "contact" in fields and defaults.requireContact and not payload.get("contact", "").strip():
        raise HTTPException(422, "Contact details are required by your lead settings")
    if "description" in fields and defaults.requireDescription and not payload.get("description", "").strip():
        raise HTTPException(422, "A requirement description is required by your lead settings")


def quote_defaults(db, data, *, existing_number=None, uploaded=False):
    shared, _ = shared_settings(db, lock=True)
    changes = {}
    if not data.valid_until:
        changes["valid_until"] = data.date + timedelta(days=shared.quotation.validity)
    if not uploaded:
        if "currency" not in data.model_fields_set:
            changes["currency"] = shared.quotation.currency
        if "tax" not in data.model_fields_set:
            changes["tax"] = shared.quotation.tax
        if "terms" not in data.model_fields_set:
            changes["terms"] = "\n".join(value for value in [shared.quotation.paymentTerms, shared.quotation.warranty, shared.quotation.notes] if value)
    if not data.number:
        if uploaded:
            raise HTTPException(422, "Enter the quotation number shown in the uploaded PDF")
        changes["number"] = existing_number or allocate_quote_number(db, data, shared)
    payload = data.model_dump(by_alias=False)
    payload.update(changes)
    try:
        return type(data).model_validate(payload), shared
    except ValidationError as error:
        raise HTTPException(422, error_details(error)) from None


def allocate_quote_number(db, data, shared):
    # Lock before reading the counter: auto numbering and settings edits share the same version.
    row = db.scalar(select(WorkspaceSettings).where(WorkspaceSettings.id == 1).with_for_update().execution_options(populate_existing=True))
    if row is None:
        row = WorkspaceSettings(id=1, data={}, version=1)
        db.add(row)
        db.flush()
    shared = SharedData.model_validate(row.data)
    prefix = shared.divisions[data.division].prefix or shared.quotation.prefix
    number = shared.quotation.nextNumber
    for _ in range(100):
        candidate = f"{prefix}-{data.date.year}-{number:05d}"
        if db.scalar(select(Quotation.id).where(Quotation.division == data.division, Quotation.number_key == candidate.casefold())) is None:
            break
        number += 1
    else:
        raise HTTPException(409, "Quotation counter conflicts with existing numbers. Ask the Owner to advance it")
    if number >= 999999999:
        raise HTTPException(409, "Quotation counter reached its limit")
    content = shared.model_dump(mode="json")
    content["quotation"]["nextNumber"] = number + 1
    result = db.execute(update(WorkspaceSettings).where(WorkspaceSettings.id == 1, WorkspaceSettings.version == row.version)
                        .values(data=content, version=row.version + 1, updated_at=now()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Quotation numbering changed. Please retry")
    return candidate


def quote_presentation(document, shared):
    division = shared.divisions[document["division"]]
    return {**document, "issuer": {**shared.company.model_dump(), "address": division.address or shared.company.address,
                                    "gst": division.gst or shared.company.gst},
            "presentation": {"showLogo": shared.quotation.showLogo, "showSignature": shared.quotation.showSignature}}


def enforce_quote_approval(status, shared, actor):
    if shared.quotation.approvalRequired and status in {"Sent", "Accepted"} and not actor.is_owner:
        raise HTTPException(403, "Only the Owner can mark quotations as Sent or Accepted while approval is required")
