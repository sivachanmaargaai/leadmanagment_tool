import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIVISION_VALUES = ("MMC", "nemilink", "ClearCode Labs", "ENGEN", "Visotonics", "Overview")
Division = Literal["MMC", "nemilink", "ClearCode Labs", "ENGEN", "Visotonics", "Overview"]
LeadStatus = Literal["New", "In Progress", "Follow-up", "Won", "Lost"]
Priority = Literal["High", "Medium", "Low"]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True,
                              serialize_by_alias=True, extra="forbid", str_strip_whitespace=True)


class UpdateModel(ApiModel):
    @model_validator(mode="before")
    @classmethod
    def reject_required_nulls(cls, value):
        if isinstance(value, dict):
            for key, item in value.items():
                if item is None and key not in {"referredBy", "referred_by", "customerId", "customer_id"}:
                    raise ValueError(f"{key} cannot be null; omit it to leave it unchanged")
        return value


class Contact(ApiModel):
    name: str = Field(default="", max_length=120)
    designation: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class ReferenceContact(Contact):
    id: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(default="", max_length=120)


def error_details(error):
    return [{"loc": ["body", *item["loc"]], "msg": item["msg"], "type": item["type"]}
            for item in error.errors(include_context=False)]
