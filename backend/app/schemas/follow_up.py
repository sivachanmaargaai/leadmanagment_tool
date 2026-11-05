from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field

from app.schemas.common import ApiModel, Division, Priority, ReferenceContact, UpdateModel

FollowUpType = Literal["Call", "Email", "Meeting", "Other"]
Outcome = Literal["Connected", "No answer", "Requested callback", "Not interested"]


class FollowUpCreate(ApiModel):
    lead_id: str = Field(alias="leadId", min_length=1, max_length=36)
    purpose: str = Field(min_length=1, max_length=200)
    type: FollowUpType = "Call"
    due_at: AwareDatetime = Field(alias="dueAt")
    assigned_to: str = Field(default="Admin", alias="assignedTo", min_length=1, max_length=100)
    priority: Priority = "Medium"
    reminder_minutes: int = Field(default=30, alias="reminderMinutes", ge=0, le=10080)
    notes: str = Field(default="", max_length=2000)


class FollowUpUpdate(UpdateModel):
    purpose: str | None = Field(default=None, min_length=1, max_length=200)
    type: FollowUpType | None = None
    due_at: AwareDatetime | None = Field(default=None, alias="dueAt")
    assigned_to: str | None = Field(default=None, alias="assignedTo", min_length=1, max_length=100)
    priority: Priority | None = None
    reminder_minutes: int | None = Field(default=None, alias="reminderMinutes", ge=0, le=10080)
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["Pending", "Completed"] | None = None
    outcome: Outcome | None = None
    completion_notes: str | None = Field(default=None, alias="completionNotes", max_length=2000)
    reschedule_reason: str | None = Field(default=None, alias="rescheduleReason", max_length=500)
    next_due_at: AwareDatetime | None = Field(default=None, alias="nextDueAt")
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)


class FollowUpResponse(ApiModel):
    customer_id: str | None = Field(default=None, alias="customerId")
    id: str
    lead_id: str = Field(alias="leadId")
    customer: str
    division: Division
    referred_by: ReferenceContact | None = Field(alias="referredBy")
    lead_source: str = Field(alias="leadSource")
    purpose: str
    type: FollowUpType
    due_at: datetime = Field(alias="dueAt")
    assigned_to: str = Field(alias="assignedTo")
    priority: Priority
    reminder_minutes: int = Field(alias="reminderMinutes")
    notes: str
    status: Literal["Pending", "Completed"]
    outcome: str
    completion_notes: str = Field(alias="completionNotes")
    completed_at: datetime | None = Field(alias="completedAt")
    history: list[dict[str, Any]]
    version: int
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class FollowUpUpdateResponse(ApiModel):
    record: FollowUpResponse
    next_follow_up: FollowUpResponse | None = Field(default=None, alias="nextFollowUp")
