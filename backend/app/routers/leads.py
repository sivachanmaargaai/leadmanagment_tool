from typing import Annotated
from datetime import datetime, timezone
from app.schemas.pagination import Page, LeadList
from app.services.pagination import collection_query, paginate
from app.services.customer_links import validate_link
from app.services.concurrency import claim_version, expected_version
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.crm_access import get_crm_db, scoped, require_record, require_admin, creation_assignment
from app.db.operations import database_operation
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.schemas.common import error_details
from app.schemas.lead import LeadCreate, LeadResponse, LeadUpdate
from app.services.settings import enforce_lead_requirements, shared_settings

router = APIRouter(prefix="/api/leads", tags=["Leads"])


def find_lead(db, lead_id):
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update().execution_options(populate_existing=True))
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return require_record(db, lead)


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead(data: LeadCreate, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        settings, _ = shared_settings(db)
        payload = data.model_dump(by_alias=False)
        if "status" not in data.model_fields_set:
            payload["status"] = settings.leads.defaultStatus
        if "priority" not in data.model_fields_set:
            payload["priority"] = settings.leads.defaultPriority
        enforce_lead_requirements(payload, settings.leads)
        validate_link(db, data.customer_id, data.customer)
        lead = Lead(**payload, assignee_user_id=creation_assignment(db))
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead


@router.get("", response_model=list[LeadResponse] | Page[LeadResponse])
def get_leads(db: Session = Depends(get_crm_db), filters: Annotated[LeadList, Query()] = LeadList()):
    with database_operation(db):
        return paginate(db, collection_query(db, Lead, filters, datetime.now(timezone.utc)), Lead, filters)


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: str, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return find_lead(db, lead_id)


@router.put("/{lead_id}", response_model=LeadResponse)
def update_lead(lead_id: str, data: LeadUpdate, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        lead = find_lead(db, lead_id)
        expected_version(db, lead, data.expected_version)
        updates = data.model_dump(exclude_unset=True, by_alias=False, exclude={"expected_version"})
        candidate = {field: getattr(lead, field) for field in LeadCreate.model_fields}
        candidate.update(updates)
        try:
            validated = LeadCreate.model_validate(candidate).model_dump(by_alias=False)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=error_details(error)) from None
        settings, _ = shared_settings(db)
        enforce_lead_requirements(validated, settings.leads, set(updates))
        validate_link(db, validated["customer_id"], validated["customer"], lead)
        claim_version(db, Lead, lead, data.expected_version)
        for field in updates:
            setattr(lead, field, validated[field])
        db.commit()
        db.refresh(lead)
        return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: str, db: Session = Depends(get_crm_db), expectedVersion: Annotated[int | None, Query(ge=1)] = None):
    with database_operation(db):
        require_admin(db)
        lead = find_lead(db, lead_id)
        expected_version(db, lead, expectedVersion)
        if db.scalar(select(FollowUp.id).where(FollowUp.lead_id == lead_id).limit(1)) is not None:
            raise HTTPException(status_code=409, detail="This lead has follow-up history and cannot be deleted")
        claim_version(db, Lead, lead, expectedVersion)
        db.delete(lead)
        db.commit()
