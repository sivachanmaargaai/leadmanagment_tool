"""Explicit CRM query and mutation policy. Display names never grant access."""
from fastapi import Depends, HTTPException
from sqlalchemy import select, false
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.models.user import User


def get_crm_db(actor=Depends(get_current_user), db=Depends(get_db)):
    previous = db.info.get("crm_actor")
    db.info["crm_actor"] = actor
    try:
        yield db
    finally:
        if previous is None:
            db.info.pop("crm_actor", None)
        else:
            db.info["crm_actor"] = previous


def actor(db):
    return db.info.get("crm_actor")


def scoped(db, query, model):
    user = actor(db)
    from app.models.quotation import Quotation
    from app.services.permissions import quotations_allowed
    if model is Quotation and not quotations_allowed(user):
        return query.where(false())
    if user is not None and user.role == "Staff":
        if model is FollowUp:
            return query.where(FollowUp.lead_id.in_(select(Lead.id).where(Lead.assignee_user_id == user.id)))
        return query.where(model.assignee_user_id == user.id)
    return query


def require_record(db, record):
    user = actor(db)
    if record is None or (user is not None and user.role == "Staff" and record.assignee_user_id != user.id):
        raise HTTPException(404, "Record not found")
    return record


def require_admin(db):
    user = actor(db)
    if user is not None and user.role != "Admin":
        raise HTTPException(403, "Only administrators can delete or reassign CRM records")


def creation_assignment(db):
    user = actor(db)
    return user.id if user is not None else None


def enforce_follow_assignment(db, payload):
    user = actor(db)
    if user is not None and user.role == "Staff":
        # This label is presentation only; access always derives from the linked lead ID.
        payload["assigned_to"] = user.name


def follow_assignee_name(db, lead, fallback):
    if lead.assignee_user_id:
        user = db.get(User, lead.assignee_user_id)
        if user is not None:
            return user.name
    return fallback
