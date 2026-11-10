from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiModel, Division, DIVISION_VALUES, Priority

DIVISIONS = list(DIVISION_VALUES)
DIVISION_PREFIXES = ["MMC", "NEM", "CCL", "ENG", "VIS", "OVW"]


class CompanySettings(ApiModel):
    name: str = Field(default="ENGEN", min_length=1, max_length=120)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=30)
    address: str = Field(default="", max_length=1000)
    gst: str = Field(default="", max_length=30)
    website: str = Field(default="", max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if value:
            from app.schemas.auth import LoginRequest
            return LoginRequest.normalized_email(value)
        return value

    @field_validator("website")
    @classmethod
    def valid_website(cls, value):
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Website must start with https:// or http://")
        return value


class DivisionSettings(ApiModel):
    name: Division
    address: str = Field(default="", max_length=1000)
    gst: str = Field(default="", max_length=30)
    prefix: str = Field(default="", max_length=20, pattern=r"^[A-Za-z0-9-]*$")


class LeadDefaults(ApiModel):
    defaultPriority: Priority = "Medium"
    defaultStatus: Literal["New", "In Progress", "Follow-up"] = "New"
    sources: list[str] = Field(default_factory=lambda: ["Website", "Referral", "Phone", "Email", "Exhibition"], max_length=30)
    followUpDays: int = Field(default=2, ge=1, le=365)
    requireContact: bool = False
    requireDescription: bool = True

    @field_validator("sources")
    @classmethod
    def clean_sources(cls, values):
        if any(not value.strip() or len(value.strip()) > 100 for value in values):
            raise ValueError("Each lead source requires 1-100 characters")
        return list(dict.fromkeys(value.strip() for value in values))


class QuotationDefaults(ApiModel):
    prefix: str = Field(default="ENG", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    nextNumber: int = Field(default=1001, ge=1, le=999999999)
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    validity: int = Field(default=15, ge=1, le=365)
    tax: float = Field(default=0, ge=0, le=100, multiple_of=0.01, allow_inf_nan=False)
    paymentTerms: str = Field(default="", max_length=3000)
    warranty: str = Field(default="", max_length=3000)
    notes: str = Field(default="", max_length=3000)
    showLogo: bool = True
    showSignature: bool = True
    approvalRequired: bool = False


class Notifications(ApiModel):
    leadPriority: bool = True
    followUp: bool = True
    overdue: bool = True
    quotationExpiry: bool = True
    reminderBefore: int = Field(default=30, ge=0, le=10080)
    sound: bool = False


class WorkspacePreferences(ApiModel):
    sidebar: Literal["Hover to expand", "Always expanded"] = "Hover to expand"
    defaultDivision: Literal["All divisions", "MMC", "nemilink", "ClearCode Labs", "ENGEN", "Visotonics", "Overview"] = "All divisions"
    rowsPerPage: int = Field(default=10, ge=5, le=100)
    dateFormat: Literal["DD MMM YYYY", "DD/MM/YYYY", "YYYY-MM-DD"] = "DD MMM YYYY"


class PersonalData(ApiModel):
    phone: str = Field(default="", max_length=30)
    designation: str = Field(default="", max_length=120)
    notifications: Notifications = Field(default_factory=Notifications)
    workspace: WorkspacePreferences = Field(default_factory=WorkspacePreferences)


class SharedData(ApiModel):
    company: CompanySettings = Field(default_factory=CompanySettings)
    divisions: dict[str, DivisionSettings] = Field(default_factory=lambda: {
        name: DivisionSettings(name=name, prefix=prefix)
        for name, prefix in zip(DIVISIONS, DIVISION_PREFIXES)
    })
    leads: LeadDefaults = Field(default_factory=LeadDefaults)
    quotation: QuotationDefaults = Field(default_factory=QuotationDefaults)

    @field_validator("divisions")
    @classmethod
    def fixed_divisions(cls, value):
        if set(value) != set(DIVISIONS) or any(item.name != key for key, item in value.items()):
            raise ValueError("Provide all six configured divisions with matching names")
        return value


class ProfileUpdate(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=30)
    designation: str = Field(default="", max_length=120)


class SettingsUpdate(ApiModel):
    expectedSharedVersion: int | None = Field(default=None, ge=1)
    expectedPersonalVersion: int | None = Field(default=None, ge=0)
    expectedProfileVersion: int | None = Field(default=None, ge=1)
    profile: ProfileUpdate | None = None
    company: CompanySettings | None = None
    divisions: dict[str, DivisionSettings] | None = None
    leads: LeadDefaults | None = None
    quotation: QuotationDefaults | None = None
    notifications: Notifications | None = None
    workspace: WorkspacePreferences | None = None

    @model_validator(mode="after")
    def versions_required(self):
        shared = any(getattr(self, key) is not None for key in ["company", "divisions", "leads", "quotation"])
        personal = any(getattr(self, key) is not None for key in ["profile", "notifications", "workspace"])
        if not shared and not personal:
            raise ValueError("Provide settings to update")
        if shared and self.expectedSharedVersion is None:
            raise ValueError("expectedSharedVersion is required")
        if personal and self.expectedPersonalVersion is None:
            raise ValueError("expectedPersonalVersion is required")
        if self.profile is not None and self.expectedProfileVersion is None:
            raise ValueError("expectedProfileVersion is required")
        if self.divisions is not None:
            SharedData.fixed_divisions(self.divisions)
        return self
