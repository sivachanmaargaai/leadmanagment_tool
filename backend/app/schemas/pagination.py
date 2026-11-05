from datetime import date as Date
from typing import Generic, Literal, TypeVar
from pydantic import Field
from app.schemas.common import ApiModel, Division, LeadStatus, Priority

T = TypeVar("T")


class Page(ApiModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    pages: int
    has_more: bool = Field(alias="hasMore")


class ListQuery(ApiModel):
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=100, alias="pageSize", ge=1, le=100)
    paged: bool = False
    q: str = Field(default="", max_length=120)
    division: Division | None = None
    assignee_user_id: str | None = Field(default=None, alias="assigneeUserId", min_length=1, max_length=36)


class LeadList(ListQuery):
    status: LeadStatus | None = None
    priority: Priority | None = None
    source: str | None = Field(default=None, max_length=100)
    customer_id: str | None = Field(default=None, alias="customerId", min_length=1, max_length=36)
    unlinked: bool = False
    customer: str | None = Field(default=None, max_length=120)


class CustomerList(ListQuery):
    type: Literal["Company", "Individual"] | None = None


class FollowUpList(ListQuery):
    status: Literal["Pending", "Completed"] | None = None
    view: Literal["All", "Today", "Overdue", "Upcoming", "Completed"] = "All"
    date: Date | None = None
    lead_id: str | None = Field(default=None, alias="leadId", max_length=36)
    customer_id: str | None = Field(default=None, alias="customerId", min_length=1, max_length=36)
    unlinked: bool = False
    customer: str | None = Field(default=None, max_length=120)
    assigned_to: str | None = Field(default=None, alias="assignedTo", max_length=120)


class QuotationList(ListQuery):
    summary: bool = False
    status: Literal["Draft", "Sent", "Accepted", "Rejected", "Expired"] | None = None
    source: Literal["Created", "Uploaded"] | None = None
    customer_id: str | None = Field(default=None, alias="customerId", min_length=1, max_length=36)
    unlinked: bool = False
    customer: str | None = Field(default=None, max_length=120)
