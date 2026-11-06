import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ApiModel


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    # Password whitespace is significant. Do not use ApiModel's string trimming.
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currentPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value):
        return LoginRequest.normalized_email(value)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    newPassword: str = Field(min_length=8, max_length=128)


class VerifyRecoveryOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challengeId: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    code: str = Field(pattern=r"^[0-9]{6}$")


class UserResponse(ApiModel):
    can_access_quotations: bool = Field(alias="canAccessQuotations")
    id: str
    email: str
    name: str
    role: Literal["Admin", "Staff"]
    is_active: bool = Field(alias="isActive")
    is_owner: bool = Field(alias="isOwner")
    version: int


class LoginResponse(ApiModel):
    access_token: str = Field(alias="accessToken")
    token_type: Literal["Bearer"] = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(alias="expiresIn")
    user: UserResponse
