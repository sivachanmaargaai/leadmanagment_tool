from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.common import ApiModel, Division, LeadStatus, Priority, ReferenceContact, UpdateModel


class LeadBase(ApiModel):
    customer_id: str | None = Field(default=None, alias="customerId", min_length=1, max_length=36)
    customer: str = Field(min_length=1, max_length=120)
    contact: str = Field(default="", max_length=150)
    division: Division
    description: str = Field(default="", max_length=10000)
    status: LeadStatus = "New"
    priority: Priority = "Medium"
    lead_source: str = Field(default="Direct Enquiry", alias="leadSource", min_length=1, max_length=100)
    referred_by: ReferenceContact | None = Field(default=None, alias="referredBy")
    reference_notes: str = Field(default="", alias="referenceNotes", max_length=2000)


class LeadCreate(LeadBase):
    @model_validator(mode="after")
    def reference_required(self):
        if self.lead_source in {"Referral", "Known Network"} and self.referred_by is None:
            raise ValueError("Select a reference contact for referral/network leads")
        return self


class LeadUpdate(UpdateModel):
    customer_id: str | None = Field(default=None, alias="customerId", min_length=1, max_length=36)
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)
    customer: str | None = Field(default=None, min_length=1, max_length=120)
    contact: str | None = Field(default=None, max_length=150)
    division: Division | None = None
    description: str | None = Field(default=None, max_length=10000)
    status: LeadStatus | None = None
    priority: Priority | None = None
    lead_source: str | None = Field(default=None, alias="leadSource", min_length=1, max_length=100)
    referred_by: ReferenceContact | None = Field(default=None, alias="referredBy")
    reference_notes: str | None = Field(default=None, alias="referenceNotes", max_length=2000)


class LeadResponse(LeadBase):
    version: int
    assignee_user_id: str | None = Field(default=None, alias="assigneeUserId")
    id: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
