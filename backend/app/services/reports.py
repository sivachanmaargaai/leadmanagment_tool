from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.services.crm_access import scoped, follow_assignee_name, actor
from app.services.permissions import quotations_allowed
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.models.quotation import Quotation

IST = timezone(timedelta(hours=5, minutes=30))
TEST_PREFIXES = ("[qa test]", "qa-demo-", "qa-check-")


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def test_record(*values):
    return any(str(value or "").strip().lower().startswith(TEST_PREFIXES) for value in values)


def within(value, filters):
    day = utc(value).astimezone(IST).date() if isinstance(value, datetime) else value
    return (not filters.start_date or day >= filters.start_date) and (not filters.end_date or day <= filters.end_date)


def lead_rows(db, filters):
    return [item for item in db.scalars(scoped(db, select(Lead), Lead)).all()
            if (not filters.division or item.division == filters.division) and within(item.created_at, filters)
            and (filters.include_test_data or not test_record(item.customer))
            and (not getattr(filters, "status", None) or item.status == filters.status)]


def effective_status(item, today):
    return "Expired" if item.status == "Sent" and date.fromisoformat(item.document["validUntil"]) < today else item.status


def quote_rows(db, filters, today):
    if not quotations_allowed(actor(db)):
        return []
    return [item for item in db.scalars(scoped(db, select(Quotation), Quotation).where(Quotation.deleted_at.is_(None))).all()
            if (not filters.division or item.division == filters.division)
            and within(date.fromisoformat(item.document["date"]), filters)
            and (filters.include_test_data or not test_record(item.customer, item.number))
            and (not getattr(filters, "status", None) or effective_status(item, today) == filters.status)]


def follow_rows(db, filters):
    leads = {item.id: item for item in db.scalars(scoped(db, select(Lead), Lead)).all()}
    result = []
    for item in db.scalars(scoped(db, select(FollowUp), FollowUp).where(FollowUp.deleted_at.is_(None))).all():
        lead = leads.get(item.lead_id)
        if lead is None or (filters.division and lead.division != filters.division):
            continue
        if not within(item.due_at, filters) or (getattr(filters, "status", None) and item.status != filters.status):
            continue
        if not filters.include_test_data and test_record(lead.customer, item.purpose):
            continue
        result.append((item, lead))
    return result


def rate(won, lost):
    return round(won * 100 / (won + lost), 2) if won + lost else 0


def breakdown(values, names=None):
    counts = Counter(values)
    return [{"name": name, "count": counts[name]} for name in (names or sorted(counts))]


def accepted_values(quotes):
    buckets = {}
    for quote in quotes:
        if quote.status != "Accepted":
            continue
        for billing, amount in quote.document["totals"].items():
            key = (quote.document["currency"], billing)
            value = buckets.setdefault(key, {"currency": key[0], "billing": billing, "count": 0,
                                             "subtotal": Decimal("0"), "tax": Decimal("0"), "total": Decimal("0")})
            value["count"] += 1
            for field in ["subtotal", "tax", "total"]:
                value[field] += Decimal(str(amount[field]))
    return [{**value, **{field: float(value[field]) for field in ["subtotal", "tax", "total"]}}
            for key, value in sorted(buckets.items())]


def metadata(filters, basis):
    return {"filters": filters.model_dump(mode="json", by_alias=True), "dateBasis": basis,
            "timezone": "Asia/Kolkata", "generatedAt": datetime.now(timezone.utc)}


def summary_report(db, filters, now):
    leads = lead_rows(db, filters)
    quotes = quote_rows(db, filters, now.astimezone(IST).date())
    followups = follow_rows(db, filters)
    won = sum(item.status == "Won" for item in leads)
    lost = sum(item.status == "Lost" for item in leads)
    result = {**metadata(filters, "Leads: created date; quotations: quotation date; follow-ups: due date (IST)"),
            "totals": {"totalLeads": len(leads), "wonLeads": won, "lostLeads": lost, "conversionRate": rate(won, lost),
                       "overdueFollowUps": sum(item.status == "Pending" and utc(item.due_at) < now for item, _ in followups),
                       "totalQuotations": len(quotes), "acceptedQuotations": sum(item.status == "Accepted" for item in quotes)},
            "acceptedValue": accepted_values(quotes)}
    result["canAccessQuotations"] = quotations_allowed(actor(db))
    if not result["canAccessQuotations"]:
        result["totals"].pop("totalQuotations")
        result["totals"].pop("acceptedQuotations")
        result.pop("acceptedValue")
        result["dateBasis"] = "Leads: created date; follow-ups: due date (IST)"
    return result



def leads_report(db, filters):
    leads = lead_rows(db, filters)
    def groups(key):
        result = defaultdict(list)
        for item in leads:
            result[key(item)].append(item)
        return [{"name": name, "total": len(items), "won": sum(x.status == "Won" for x in items),
                 "lost": sum(x.status == "Lost" for x in items),
                 "conversionRate": rate(sum(x.status == "Won" for x in items), sum(x.status == "Lost" for x in items))}
                for name, items in sorted(result.items())]
    references = defaultdict(list)
    for item in leads:
        if item.lead_source in {"Referral", "Known Network"} and item.referred_by:
            ref = item.referred_by
            # Names alone do not merge different people with the same display name.
            identity = (ref.get("id") or ref.get("email") or ref.get("phone") or ref.get("name", ""),
                        ref.get("name", ""), ref.get("company", ""), item.lead_source)
            references[identity].append(item)
    return {**metadata(filters, "Lead created date (IST)"),
            "byStatus": breakdown((x.status for x in leads), ["New", "In Progress", "Follow-up", "Won", "Lost"]),
            "byPriority": breakdown((x.priority for x in leads), ["High", "Medium", "Low"]),
            "byDivision": groups(lambda x: x.division), "bySource": groups(lambda x: x.lead_source or "Unspecified"),
            "trend": groups(lambda x: utc(x.created_at).astimezone(IST).strftime("%Y-%m")),
            "referrals": [{"name": key[1], "company": key[2], "source": key[3], "total": len(items),
                           "won": sum(x.status == "Won" for x in items)} for key, items in sorted(references.items())],
            "rows": [{"id": x.id, "customer": x.customer, "division": x.division, "status": x.status,
                      "priority": x.priority, "source": x.lead_source, "reference": (x.referred_by or {}).get("name", ""),
                      "createdAt": utc(x.created_at)} for x in sorted(leads, key=lambda x: utc(x.created_at), reverse=True)]}


def sales_report(db, filters, now):
    today = now.astimezone(IST).date()
    quotes = quote_rows(db, filters, today)
    return {**metadata(filters, "Quotation date; Sent documents past valid-until are Expired (IST)"),
            "byStatus": breakdown((effective_status(x, today) for x in quotes), ["Draft", "Sent", "Accepted", "Rejected", "Expired"]),
            "acceptedValue": accepted_values(quotes),
            "rows": [{"id": x.id, "number": x.number, "customer": x.customer, "division": x.division,
                      "date": x.document["date"], "validUntil": x.document["validUntil"], "status": effective_status(x, today),
                      "currency": x.document["currency"], "totals": x.document["totals"], "source": x.source}
                     for x in sorted(quotes, key=lambda x: (x.document["date"], x.number), reverse=True)]}


def followups_report(db, filters, now):
    records = follow_rows(db, filters)
    rows = [{"id": x.id, "customer": lead.customer, "division": lead.division, "purpose": x.purpose,
             "dueAt": utc(x.due_at), "assignedTo": follow_assignee_name(db, lead, x.assigned_to), "status": x.status, "priority": x.priority,
             "overdue": x.status == "Pending" and utc(x.due_at) < now,
             "completedAt": utc(x.completed_at) if x.completed_at else None, "type": x.type} for x, lead in records]
    def counts(items):
        return {"total": len(items), "pending": sum(x["status"] == "Pending" for x in items),
                "completed": sum(x["status"] == "Completed" for x in items), "overdue": sum(x["overdue"] for x in items)}
    staff = sorted({x["assignedTo"] for x in rows})
    return {**metadata(filters, "Follow-up due date (IST); completed tasks remain in their due-date period"),
            "summary": counts(rows), "byStaff": [{"name": name, **counts([x for x in rows if x["assignedTo"] == name])} for name in staff],
            "byType": breakdown(x["type"] for x in rows), "rows": sorted(rows, key=lambda x: x["dueAt"])}
