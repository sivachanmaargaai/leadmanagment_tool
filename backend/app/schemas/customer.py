from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiModel, Contact, Division, ReferenceContact, UpdateModel


class CustomerBase(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    type: Literal["Company", "Individual"] = "Company"
    divisions: list[Division] = Field(default_factory=list)
    contacts: list[Contact] = Field(default_factory=list)
    address: str = Field(default="", max_length=500)
    city: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    postcode: str = Field(default="", max_length=20)
    gst: str = Field(default="", max_length=30)
    assigned_to: str = Field(default="Admin", alias="assignedTo", min_length=1, max_length=100)
    notes: str = Field(default="", max_length=10000)
    lead_source: str = Field(default="", alias="leadSource", max_length=100)
    referred_by: ReferenceContact | None = Field(default=None, alias="referredBy")
    reference_notes: str = Field(default="", alias="referenceNotes", max_length=2000)
    aliases: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("divisions")
    @classmethod
    def unique_divisions(cls, value):
        return list(dict.fromkeys(value))


class CustomerCreate(CustomerBase):
    @model_validator(mode="after")
    def required_details(self):
        if not self.divisions:
            raise ValueError("Select at least one division")
        if not self.contacts or not (self.contacts[0].phone or self.contacts[0].email):
            raise ValueError("Enter a primary phone number or email address")
        if self.lead_source in {"Referral", "Known Network"} and self.referred_by is None:
            raise ValueError("Select a reference contact for referral/network customers")
        return self


class CustomerUpdate(UpdateModel):
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: Literal["Company", "Individual"] | None = None
    divisions: list[Division] | None = None
    contacts: list[Contact] | None = None
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    postcode: str | None = Field(default=None, max_length=20)
    gst: str | None = Field(default=None, max_length=30)
    assigned_to: str | None = Field(default=None, alias="assignedTo", min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=10000)
    lead_source: str | None = Field(default=None, alias="leadSource", max_length=100)
    referred_by: ReferenceContact | None = Field(default=None, alias="referredBy")
    reference_notes: str | None = Field(default=None, alias="referenceNotes", max_length=2000)
    aliases: list[str] | None = None
    history: list[dict[str, Any]] | None = None


class CustomerResponse(CustomerBase):
    lead_count: int = Field(default=0, alias="leadCount")
    stage: str = "Prospect"
    version: int
    assignee_user_id: str | None = Field(default=None, alias="assigneeUserId")
    id: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
