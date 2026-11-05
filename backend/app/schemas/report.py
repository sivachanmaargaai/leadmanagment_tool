from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import ApiModel, Division, LeadStatus


class ReportFilters(ApiModel):
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")
    division: Division | None = None
    include_test_data: bool = Field(default=False, alias="includeTestData")

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Start date must be on or before end date")
        return self


class LeadReportFilters(ReportFilters):
    status: LeadStatus | None = None


class SalesReportFilters(ReportFilters):
    status: Literal["Draft", "Sent", "Accepted", "Rejected", "Expired"] | None = None


class FollowUpReportFilters(ReportFilters):
    status: Literal["Pending", "Completed"] | None = None
