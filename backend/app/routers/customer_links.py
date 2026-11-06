from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, update
from app.schemas.common import ApiModel
from app.services.crm_access import get_crm_db, require_admin, actor
from app.services.concurrency import claim_version, expected_version
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.quotation import Quotation
from app.models.user import UserAuditEvent
from app.db.operations import database_operation

router = APIRouter(prefix="/api/customer-links", tags=["Customer links"])


class LinkChange(ApiModel):
    customerId: str | None = Field(min_length=1, max_length=36)
    expectedVersion: int = Field(ge=1)


@router.put("/{module}/{record_id}")
def link(module: Literal["leads", "quotations"], record_id: str, data: LinkChange, db=Depends(get_crm_db)):
    require_admin(db)
    with database_operation(db):
        model = Lead if module == "leads" else Quotation
        item = db.scalar(select(model).where(model.id == record_id).with_for_update().execution_options(populate_existing=True))
        if item is None:
            raise HTTPException(404, "Record not found")
        expected_version(db, item, data.expectedVersion)
        if data.customerId is not None and db.scalar(select(Customer.id).where(Customer.id == data.customerId).with_for_update()) is None:
            raise HTTPException(404, "Customer not found")
        previous = item.customer_id
        if model is Quotation and item.deleted_at is not None:
            # Archived documents retain history; only this Admin metadata route can relink them.
            changed = db.execute(update(model).where(model.id == item.id, model.version == data.expectedVersion).values(version=model.version + 1).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                raise HTTPException(409, "Record changed. Reload before linking")
            db.refresh(item)
        else:
            claim_version(db, model, item, data.expectedVersion)
        item.customer_id = data.customerId
        db.add(UserAuditEvent(actor_id=actor(db).id, target_id=actor(db).id, action="Customer link changed",
                             changes={"module": module, "recordId": item.id, "previousCustomerId": previous, "customerId": data.customerId}))
        # Link metadata only: preserve document names, JSON snapshots and PDF bytes.
        db.commit()
        return {"id": item.id, "customerId": item.customer_id, "version": item.version}
