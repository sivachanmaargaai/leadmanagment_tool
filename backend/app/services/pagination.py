from datetime import datetime, time, timedelta, timezone
from sqlalchemy import Text, case, cast, func, or_, select
from app.models.lead import Lead
from app.models.customer import Customer
from app.models.follow_up import FollowUp
from app.models.quotation import Quotation
from app.models.user import User
from app.services.crm_access import scoped

IST = timezone(timedelta(hours=5, minutes=30))


def search(query, text, columns):
    if text:
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(*(cast(column, Text).ilike("%" + escaped + "%", escape="\\") for column in columns)))
    return query


def collection_query(db, model, filters, at):
    query = scoped(db, select(model), model)
    if model in {FollowUp, Quotation}:
        query = query.where(model.deleted_at.is_(None))
    if model is not Customer:
        column = Lead.customer_id if model is FollowUp else model.customer_id
        if filters.customer_id:
            query = query.where(column == filters.customer_id)
        if filters.unlinked:
            query = query.where(column.is_(None))
    if model is FollowUp:
        query = query.join(Lead, Lead.id == FollowUp.lead_id).outerjoin(User, User.id == Lead.assignee_user_id)
        if filters.division:
            query = query.where(Lead.division == filters.division)
        if filters.assignee_user_id:
            query = query.where(Lead.assignee_user_id == filters.assignee_user_id)
        if filters.lead_id:
            query = query.where(FollowUp.lead_id == filters.lead_id)
        if filters.assigned_to:
            query = query.where(func.coalesce(User.name, FollowUp.assigned_to) == filters.assigned_to)
        if filters.customer:
            query = query.where(func.lower(Lead.customer) == filters.customer.lower())
        if filters.status:
            query = query.where(FollowUp.status == filters.status)
        today = at.astimezone(IST).date()
        start = datetime.combine(filters.date or today, time.min, IST).astimezone(timezone.utc)
        if filters.date:
            query = query.where(FollowUp.due_at >= start, FollowUp.due_at < start + timedelta(days=1))
        day_start = datetime.combine(today, time.min, IST).astimezone(timezone.utc)
        if filters.view == "Completed":
            query = query.where(FollowUp.status == "Completed")
        elif filters.view != "All":
            query = query.where(FollowUp.status == "Pending")
            if filters.view == "Today":
                query = query.where(FollowUp.due_at >= day_start, FollowUp.due_at < day_start + timedelta(days=1))
            elif filters.view == "Overdue":
                query = query.where(FollowUp.due_at < at)
            else:
                query = query.where(FollowUp.due_at >= day_start + timedelta(days=1))
        return search(query, filters.q, [Lead.customer, Lead.referred_by, FollowUp.purpose, FollowUp.notes, func.coalesce(User.name, FollowUp.assigned_to)])
    if filters.assignee_user_id:
        query = query.where(model.assignee_user_id == filters.assignee_user_id)
    if filters.division:
        query = query.where(cast(Customer.divisions, Text).contains('"' + filters.division + '"')) if model is Customer else query.where(model.division == filters.division)
    if model is Customer:
        if filters.type:
            query = query.where(Customer.type == filters.type)
        return search(query, filters.q, [Customer.name, Customer.contacts, Customer.referred_by, Customer.aliases, Customer.city, Customer.gst])
    if filters.customer:
        query = query.where(func.lower(model.customer) == filters.customer.lower())
    if model is Lead:
        for key in ("status", "priority"):
            if getattr(filters, key):
                query = query.where(getattr(Lead, key) == getattr(filters, key))
        if filters.source:
            query = query.where(Lead.lead_source == filters.source)
        return search(query, filters.q, [Lead.customer, Lead.contact, Lead.description, Lead.status, Lead.priority, Lead.lead_source, Lead.referred_by])
    if filters.status:
        status = case(((Quotation.status == "Sent") & (Quotation.document["validUntil"].as_string() < at.astimezone(IST).date().isoformat()), "Expired"), else_=Quotation.status)
        query = query.where(status == filters.status)
    if filters.source:
        query = query.where(Quotation.source == filters.source)
    return search(query, filters.q, [Quotation.number, Quotation.customer, Quotation.division])


def paginate(db, query, model, filters, render=lambda item: item, render_many=None):
    # A unique tie breaker avoids repeated/skipped rows with identical timestamps.
    order = (FollowUp.due_at.asc(), FollowUp.id.asc()) if model is FollowUp else (model.created_at.desc(), model.id.desc())
    rows = db.scalars(query.order_by(*order).offset((filters.page - 1) * filters.page_size).limit(filters.page_size)).all()
    items = render_many(rows) if render_many else [render(item) for item in rows]
    if not filters.paged:
        return items
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    pages = max(1, (total + filters.page_size - 1) // filters.page_size)
    return {"items": items, "total": total, "page": filters.page, "pageSize": filters.page_size,
            "pages": pages, "hasMore": filters.page < pages}
