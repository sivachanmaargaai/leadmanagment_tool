"""Explicit profile relationships; display names remain historical snapshots."""
from fastapi import HTTPException
from sqlalchemy import select
from app.models.customer import Customer
from app.services.crm_access import require_record


def validate_link(db, customer_id, name, existing=None):
    if existing is not None and existing.customer_id == customer_id:
        # A separately reassigned profile must not break edits to a visible enquiry.
        if customer_id and name != existing.customer:
            raise HTTPException(422, "Clear the customer link or select a profile before changing the customer name")
        return
    if customer_id is None:
        return
    profile = db.scalar(select(Customer).where(Customer.id == customer_id).with_for_update())
    require_record(db, profile)
    if name != profile.name:
        raise HTTPException(422, "Use the selected customer's name, or clear the customer link")
