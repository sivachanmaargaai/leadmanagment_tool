"""SQL aggregates and bounded dashboard previews, independent of register size."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case, or_
from sqlalchemy.orm import Session
from app.services.crm_access import get_crm_db, scoped
from app.services.pagination import collection_query, IST
from app.schemas.pagination import LeadList, CustomerList, QuotationList, FollowUpList
from app.schemas.lead import LeadResponse
from app.schemas.common import Division
from app.models.lead import Lead
from app.models.customer import Customer
from app.models.quotation import Quotation
from app.models.follow_up import FollowUp
from app.routers.followups import response as follow_response
from app.db.operations import database_operation

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])


def count(db, query):
    return db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))


def metrics(db, division=None, assigned_to=None):
    at = datetime.now(timezone.utc)
    base = collection_query(db, Lead, LeadList(division=division), at)
    source = base.subquery()
    pipeline = dict(db.execute(select(source.c.status, func.count()).group_by(source.c.status)).all())
    active = count(db, base.where(Lead.status.notin_(["Won", "Lost"])))
    high = count(db, base.where(Lead.status.notin_(["Won", "Lost"]), Lead.priority == "High"))
    quotes = collection_query(db, Quotation, QuotationList(division=division), at).subquery()
    effective = case(((quotes.c.status == "Sent") & (quotes.c.document["validUntil"].as_string() < at.astimezone(IST).date().isoformat()), "Expired"), else_=quotes.c.status)
    quote_counts = dict(db.execute(select(effective, func.count()).group_by(effective)).all())
    tasks = {view: count(db, collection_query(db, FollowUp, FollowUpList(division=division, assignedTo=assigned_to, view=view), at))
             for view in ["All", "Today", "Overdue", "Upcoming", "Completed"]}
    customers = collection_query(db, Customer, CustomerList(division=division), at)
    won_customers = scoped(db, select(Lead.customer_id).where(Lead.status == "Won", Lead.customer_id.is_not(None)), Lead)
    converted = count(db, customers.where(Customer.id.in_(won_customers)))
    total_customers = count(db, customers)
    return {"leads": {"total": sum(pipeline.values()), "active": active, "won": pipeline.get("Won", 0), "high": high, "pipeline": pipeline},
            "quotations": {"Total": sum(quote_counts.values()), **quote_counts}, "followUps": tasks,
            "customers": {"Total customers": total_customers, "Prospects": total_customers - converted, "Converted customers": converted}}


@router.get("/metrics")
def get_metrics(division: Division | None = None, assignedTo: str | None = Query(default=None, max_length=120), db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return metrics(db, division, assignedTo)


@router.get("/overview")
def overview(division: Division | None = None, db: Session = Depends(get_crm_db)):
    with database_operation(db):
        at = datetime.now(timezone.utc)
        leads = collection_query(db, Lead, LeadList(division=division), at)
        recent = db.scalars(leads.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(5)).all()
        high = db.scalars(leads.where(Lead.priority == "High", Lead.status.notin_(["Won", "Lost"])).order_by(Lead.created_at.desc(), Lead.id.desc()).limit(20)).all()
        tasks = collection_query(db, FollowUp, FollowUpList(division=division, status="Pending"), at)
        queue = db.scalars(tasks.order_by(FollowUp.due_at, FollowUp.id).limit(3)).all()
        if db.bind.dialect.name == "sqlite":
            eligible = (func.julianday(FollowUp.due_at) - func.julianday(at)) * 1440 <= FollowUp.reminder_minutes
        else:
            eligible = FollowUp.due_at <= at + FollowUp.reminder_minutes * __import__('sqlalchemy').text("INTERVAL '1 minute'")
        reminders = db.scalars(tasks.where(eligible).order_by(FollowUp.due_at, FollowUp.id).limit(20)).all()
        quotes = collection_query(db, Quotation, QuotationList(division=division), at)
        expiring = db.scalars(quotes.where(Quotation.status.in_(["Sent", "Expired"]), Quotation.document["validUntil"].as_string() <= (at.astimezone(IST).date() + timedelta(days=2)).isoformat()).order_by(Quotation.document["validUntil"].as_string(), Quotation.id).limit(20)).all()
        return {"metrics": metrics(db, division), "recentLeads": [LeadResponse.model_validate(row) for row in recent],
                "queue": [follow_response(row, db) for row in queue], "alertLeads": [LeadResponse.model_validate(row) for row in high],
                "alertFollowUps": [follow_response(row, db) for row in reminders],
                "alertQuotes": [{"id": row.id, "number": row.number, "customer": row.customer, "division": row.division, "status": row.status, "validUntil": row.document.get("validUntil", "")} for row in expiring],
                "alertLimit": 20}
