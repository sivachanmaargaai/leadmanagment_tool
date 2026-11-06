from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.services.crm_access import get_crm_db
from app.db.operations import database_operation
from app.schemas.report import ReportFilters, LeadReportFilters, SalesReportFilters, FollowUpReportFilters
from app.services.reports import summary_report, leads_report, sales_report, followups_report
from app.core.security import require_quotation_user

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/summary")
def summary(filters: Annotated[ReportFilters, Query()], db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return summary_report(db, filters, datetime.now(timezone.utc))


@router.get("/leads")
def leads(filters: Annotated[LeadReportFilters, Query()], db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return leads_report(db, filters)


@router.get("/sales", dependencies=[Depends(require_quotation_user)])
def sales(filters: Annotated[SalesReportFilters, Query()], db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return sales_report(db, filters, datetime.now(timezone.utc))


@router.get("/follow-ups")
def followups(filters: Annotated[FollowUpReportFilters, Query()], db: Session = Depends(get_crm_db)):
    with database_operation(db):
        return followups_report(db, filters, datetime.now(timezone.utc))
