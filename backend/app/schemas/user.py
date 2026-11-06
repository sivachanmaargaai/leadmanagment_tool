from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.auth import LoginRequest, UserResponse


class UserCreate(LoginRequest):
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["Admin", "Staff"] = "Staff"

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a name")
        return value


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    expected_version: int = Field(alias="expectedVersion", ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: Literal["Admin", "Staff"] | None = None
    is_active: bool | None = Field(default=None, alias="isActive")

    @model_validator(mode="before")
    @classmethod
    def require_changes(cls, value):
        if isinstance(value, dict):
            if any(item is None for item in value.values()):
                raise ValueError("Omit unchanged fields rather than sending null")
            if not set(value) - {"expectedVersion", "expected_version"}:
                raise ValueError("Provide at least one field to update")
        return value

    @field_validator("name")
    @classmethod
    def trimmed_name(cls, value):
        return UserCreate.nonempty_name(value)

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value):
        return LoginRequest.normalized_email(value)


class ManagedUser(UserResponse):
    created_at: datetime = Field(alias="createdAt")


class UserDirectory(BaseModel):
    users: list[ManagedUser]
    canManageUsers: bool
    canManageRolePermissions: bool = False
    adminCount: int | None
    adminLimit: int = 2
    scope: Literal["All accounts", "Staff only", "My profile"]
