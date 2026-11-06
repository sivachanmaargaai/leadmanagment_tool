from typing import Annotated
from datetime import datetime, timezone
from app.schemas.pagination import Page, CustomerList
from app.services.pagination import collection_query, paginate
from app.services.concurrency import claim_version, expected_version
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import ValidationError
from sqlalchemy import func, select, or_, and_, case
from sqlalchemy.orm import Session

from app.services.crm_access import get_crm_db, scoped, require_record, require_admin, creation_assignment, enforce_follow_assignment, actor
from app.db.operations import database_operation
from app.models.customer import Customer
from app.models.lead import Lead
from app.schemas.common import error_details
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["Customers"])


def find_customer(db, customer_id):
    customer = db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update().execution_options(populate_existing=True))
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return require_record(db, customer)


def profile_responses(rows, db):
    if not rows:
        return []
    counts = {customer_id: (total, won) for customer_id, total, won in db.execute(scoped(db, select(Lead.customer_id, func.count(), func.sum(case((Lead.status == "Won", 1), else_=0))), Lead).where(Lead.customer_id.in_([row.id for row in rows])).group_by(Lead.customer_id)).all()}
    return [CustomerResponse.model_validate(row).model_copy(update={"lead_count": counts.get(row.id, (0, 0))[0], "stage": "Converted Customer" if counts.get(row.id, (0, 0))[1] else "Prospect"}) for row in rows]


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(data: CustomerCreate, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        payload = data.model_dump(by_alias=False)
        if actor(db) is not None:
            payload["assigned_to"] = actor(db).name
        customer = Customer(**payload, assignee_user_id=creation_assignment(db))
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return profile_responses([customer], db)[0]


@router.get("", response_model=list[CustomerResponse] | Page[CustomerResponse])
def get_customers(db: Session = Depends(get_crm_db), filters: Annotated[CustomerList, Query()] = CustomerList()):
    with database_operation(db):
        return paginate(db, collection_query(db, Customer, filters, datetime.now(timezone.utc)), Customer, filters, render_many=lambda rows: profile_responses(rows, db))


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return profile_responses([find_customer(db, customer_id)], db)[0]


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: str, data: CustomerUpdate, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        customer = find_customer(db, customer_id)
        expected_version(db, customer, data.expected_version)
        updates = data.model_dump(exclude_unset=True, by_alias=False, exclude={"expected_version"})
        candidate = {field: getattr(customer, field) for field in CustomerCreate.model_fields}
        enforce_follow_assignment(db, updates)
        candidate.update(updates)
        try:
            validated = CustomerCreate.model_validate(candidate).model_dump(by_alias=False)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=error_details(error)) from None
        claim_version(db, Customer, customer, data.expected_version)
        for field in updates:
            setattr(customer, field, validated[field])
        db.commit()
        db.refresh(customer)
        return profile_responses([customer], db)[0]


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: str, db: Session = Depends(get_crm_db), expectedVersion: Annotated[int | None, Query(ge=1)] = None):
    with database_operation(db):
        require_admin(db)
        customer = find_customer(db, customer_id)
        expected_version(db, customer, expectedVersion)
        # Retain unresolved legacy references as well as explicit foreign keys.
        names = {name.strip().lower() for name in [customer.name, *customer.aliases] if name.strip()}
        linked = db.scalar(select(Lead.id).where(or_(Lead.customer_id == customer.id, and_(Lead.customer_id.is_(None), func.lower(func.trim(Lead.customer)).in_(names)))).limit(1))
        if linked is not None:
            raise HTTPException(status_code=409, detail="This customer has linked leads. Reassign or archive them before deleting the profile")
        from app.models.quotation import Quotation
        linked_quote = db.scalar(select(Quotation.id).where(or_(Quotation.customer_id == customer.id, and_(Quotation.customer_id.is_(None), func.lower(func.trim(Quotation.customer)).in_(names)))).limit(1))
        if linked_quote is not None:
            raise HTTPException(status_code=409, detail="This customer has retained quotations. Keep the customer profile for its document history")
        claim_version(db, Customer, customer, expectedVersion)
        db.delete(customer)
        db.commit()
