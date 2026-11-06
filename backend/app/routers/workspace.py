"""SQL aggregates and bounded dashboard previews, independent of register size."""
from datetime import datetime, timedelta, timezone, time
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case, text, and_, or_, false
from sqlalchemy.orm import Session
from app.services.crm_access import get_crm_db, scoped, actor
from app.services.permissions import quotations_allowed
from app.services.pagination import collection_query, IST
from app.schemas.pagination import LeadList, CustomerList, QuotationList, FollowUpList
from app.schemas.lead import LeadResponse
from app.schemas.common import Division
from app.models.lead import Lead
from app.models.customer import Customer
from app.models.quotation import Quotation
from app.models.follow_up import FollowUp
from app.routers.followups import responses as follow_responses
from app.db.operations import database_operation

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])


def metrics(db, division=None, assigned_to=None):
    at = datetime.now(timezone.utc)
    source = collection_query(db, Lead, LeadList(division=division), at).subquery()
    groups = db.execute(select(source.c.status, source.c.priority, func.count()).group_by(source.c.status, source.c.priority)).all()
    pipeline = {}
    active = high = 0
    for status, priority, total in groups:
        pipeline[status] = pipeline.get(status, 0) + total
        if status not in {"Won", "Lost"}:
            active += total
            if priority == "High":
                high += total
    quote_counts = {}
    if quotations_allowed(actor(db)):
        quotes = collection_query(db, Quotation, QuotationList(division=division), at).subquery()
        effective = case(((quotes.c.status == "Sent") & (quotes.c.document["validUntil"].as_string() < at.astimezone(IST).date().isoformat()), "Expired"), else_=quotes.c.status)
        quote_counts = dict(db.execute(select(effective, func.count()).group_by(effective)).all())
    tasks = collection_query(db, FollowUp, FollowUpList(division=division, assignedTo=assigned_to), at).subquery()
    start = datetime.combine(at.astimezone(IST).date(), time.min, IST).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    pending = tasks.c.status == "Pending"
    def tally(condition):
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)
    task_values = db.execute(select(func.count(),
        tally(and_(pending, tasks.c.due_at >= start, tasks.c.due_at < end)),
        tally(and_(pending, tasks.c.due_at < at)),
        tally(and_(pending, tasks.c.due_at >= end)), tally(tasks.c.status == "Completed")).select_from(tasks)).one()
    task_counts = dict(zip(["All", "Today", "Overdue", "Upcoming", "Completed"], task_values))
    customers = collection_query(db, Customer, CustomerList(division=division), at).subquery()
    won_customers = scoped(db, select(Lead.customer_id).where(Lead.status == "Won", Lead.customer_id.is_not(None)), Lead)
    total_customers, converted = db.execute(select(func.count(), tally(customers.c.id.in_(won_customers))).select_from(customers)).one()
    return {"leads": {"total": sum(pipeline.values()), "active": active, "won": pipeline.get("Won", 0), "high": high, "pipeline": pipeline},
            **({"quotations": {"Total": sum(quote_counts.values()), **quote_counts}} if quotations_allowed(actor(db)) else {}), "followUps": task_counts,
            "customers": {"Total customers": total_customers, "Prospects": total_customers - converted, "Converted customers": converted}}


@router.get("/metrics")
def get_metrics(division: Division | None = None, assignedTo: str | None = Query(default=None, max_length=120), db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return metrics(db, division, assignedTo)


@router.get("/overview")
def overview(division: Division | None = None, leadPriority: bool = True, followUp: bool = True, overdue: bool = True, quotationExpiry: bool = True, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        at = datetime.now(timezone.utc)
        leads = collection_query(db, Lead, LeadList(division=division), at)
        recent = db.scalars(leads.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(5)).all()
        high = db.scalars(leads.where(Lead.priority == "High", Lead.status.notin_(["Won", "Lost"])).order_by(Lead.created_at.desc(), Lead.id.desc()).limit(20)).all() if leadPriority else []
        tasks = collection_query(db, FollowUp, FollowUpList(division=division, status="Pending"), at)
        queue = db.scalars(tasks.order_by(FollowUp.due_at, FollowUp.id).limit(3)).all()
        if db.bind.dialect.name == "sqlite":
            eligible = (func.julianday(FollowUp.due_at) - func.julianday(at)) * 1440 <= FollowUp.reminder_minutes
        else:
            eligible = FollowUp.due_at <= at + FollowUp.reminder_minutes * text("INTERVAL '1 minute'")
        enabled = or_(FollowUp.due_at < at if overdue else false(), and_(FollowUp.due_at >= at, eligible) if followUp else false())
        reminders = db.scalars(tasks.where(enabled).order_by(FollowUp.due_at, FollowUp.id).limit(20)).all()
        quotes = collection_query(db, Quotation, QuotationList(division=division), at)
        expiring = db.scalars(quotes.where(Quotation.status.in_(["Sent", "Expired"]), Quotation.document["validUntil"].as_string() <= (at.astimezone(IST).date() + timedelta(days=2)).isoformat()).order_by(Quotation.document["validUntil"].as_string(), Quotation.id).limit(20)).all() if quotationExpiry and quotations_allowed(actor(db)) else []
        return {"metrics": metrics(db, division), "recentLeads": [LeadResponse.model_validate(row) for row in recent],
                "queue": follow_responses(queue, db), "alertLeads": [LeadResponse.model_validate(row) for row in high],
                "alertFollowUps": follow_responses(reminders, db),
                **({"alertQuotes": [{"id": row.id, "number": row.number, "customer": row.customer, "division": row.division, "status": row.status, "validUntil": row.document.get("validUntil", "")} for row in expiring]} if quotations_allowed(actor(db)) else {}),
                "alertLimit": 20}
