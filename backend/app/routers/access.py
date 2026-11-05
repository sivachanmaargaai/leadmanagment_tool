from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from app.db.operations import database_operation
from app.models.lead import Lead
from app.models.customer import Customer
from app.models.quotation import Quotation
from app.models.user import User, UserAuditEvent
from app.services.crm_access import actor, get_crm_db, require_admin
from app.services.concurrency import expected_version, claim_version
from app.services.pagination import search

router = APIRouter(prefix="/api/access", tags=["CRM assignments"])
MODELS = {"leads": Lead, "customers": Customer, "quotations": Quotation}


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigneeUserId: str | None = Field(max_length=36)
    expectedAssigneeUserId: str | None = Field(max_length=36)
    expectedVersion: int | None = Field(default=None, ge=1)


@router.get("/assignments")
def assignments(module: Literal["leads", "customers", "quotations"] = "leads",
                offset: int = Query(0, ge=0, le=1000000), limit: int = Query(25, ge=1, le=100), q: str = Query("", max_length=120), db=Depends(get_crm_db)):
    require_admin(db)
    with database_operation(db):
        model = MODELS[module]
        query = select(model).order_by(model.created_at.desc(), model.id)
        if model is Quotation:
            query = query.where(Quotation.deleted_at.is_(None))
        query = search(query, q.strip(), [Customer.name] if model is Customer else [Quotation.number, Quotation.customer] if model is Quotation else [Lead.customer, Lead.contact])
        records = db.scalars(query.offset(offset).limit(limit + 1)).all()
        users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.name, User.id)).all()
        return {"module": module, "hasMore": len(records) > limit,
                "users": [{"id": user.id, "name": user.name, "role": user.role} for user in users],
                "records": [{"id": item.id, "label": item.name if model is Customer else item.number + " · " + item.customer if model is Quotation else item.customer,
                             "assigneeUserId": item.assignee_user_id, "version": item.version} for item in records[:limit]]}


@router.put("/assignments/{module}/{record_id}")
def assign(module: Literal["leads", "customers", "quotations"], record_id: str, data: Assignment, db=Depends(get_crm_db)):
    require_admin(db)
    with database_operation(db):
        model = MODELS[module]
        item = db.scalar(select(model).where(model.id == record_id).with_for_update().execution_options(populate_existing=True))
        if item is None or (model is Quotation and item.deleted_at is not None):
            raise HTTPException(404, "Record not found")
        expected_version(db, item, data.expectedVersion)
        if item.assignee_user_id != data.expectedAssigneeUserId:
            raise HTTPException(409, "Assignment changed. Reload before retrying")
        user = db.get(User, data.assigneeUserId) if data.assigneeUserId else None
        if data.assigneeUserId is not None and (user is None or not user.is_active):
            raise HTTPException(422, "Select an active account")
        claim_version(db, model, item, data.expectedVersion)
        previous = item.assignee_user_id
        item.assignee_user_id = data.assigneeUserId
        if model is Customer:
            item.assigned_to = user.name if user else "Unassigned"
        db.add(UserAuditEvent(actor_id=actor(db).id, target_id=user.id if user else actor(db).id,
                             action="CRM assignment changed", changes={"module": module, "recordId": item.id,
                             "previousAssigneeUserId": previous, "assigneeUserId": data.assigneeUserId}))
        db.commit()
        return {"id": item.id, "assigneeUserId": item.assignee_user_id, "version": item.version}
