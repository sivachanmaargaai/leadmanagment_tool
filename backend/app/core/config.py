from typing import Literal
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from urllib.parse import urlsplit
import re
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    COOKIE_SECURE: bool = False
    ACCESS_TOKEN_MINUTES: int = Field(default=15, ge=1, le=60)
    SESSION_DAYS: int = Field(default=7, ge=1, le=30)
    PASSWORD_RECOVERY_ENABLED: bool = False
    RESET_LINK_MINUTES: int = Field(default=15, ge=5, le=60)
    RESET_BASE_URL: str = "http://localhost:5173"
    SMTP_HOST: str = ""
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_SECURITY: Literal["starttls", "ssl"] = "starttls"
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: SecretStr = SecretStr("")
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = Field(default="ENGEN CRM", max_length=120)
    SMTP_TIMEOUT_SECONDS: int = Field(default=10, ge=1, le=30)
    RATE_LIMIT_ENABLED: bool = True
    API_IP_PER_MINUTE: int = Field(default=600, ge=1, le=10000)
    API_IP_BURST_PER_10_SECONDS: int = Field(default=100, ge=1, le=2000)
    API_USER_PER_MINUTE: int = Field(default=300, ge=1, le=10000)
    API_USER_WRITES_PER_MINUTE: int = Field(default=60, ge=1, le=2000)
    LOGIN_IP_PER_15_MINUTES: int = Field(default=20, ge=1, le=200)
    LOGIN_EMAIL_PER_15_MINUTES: int = Field(default=10, ge=1, le=100)
    REQUEST_JSON_MAX_BYTES: int = Field(default=1048576, ge=1024, le=4194304)
    REQUEST_AUTH_MAX_BYTES: int = Field(default=16384, ge=1024, le=65536)
    REQUEST_UPLOAD_MAX_BYTES: int = Field(default=12582912, ge=1048576, le=16777216)
    REQUEST_HEADER_MAX_BYTES: int = Field(default=16384, ge=1024, le=65536)
    REQUEST_MAX_HEADERS: int = Field(default=100, ge=10, le=200)
    REQUEST_URL_MAX_BYTES: int = Field(default=4096, ge=256, le=8192)
    REQUEST_BODY_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)
    OPS_DIRECTORY: Path = Path(__file__).resolve().parents[2] / "var"
    PG_BIN_DIRECTORY: str = ""
    BACKUP_RETENTION_COUNT: int = Field(default=7, ge=2, le=90)
    BACKUP_MAX_AGE_HOURS: int = Field(default=30, ge=1, le=720)
    BACKUP_TOOL_TIMEOUT_SECONDS: int = Field(default=600, ge=10, le=7200)
    BACKUP_RESTORE_ADMIN_URL: SecretStr = SecretStr("")
    OPS_LOG_ENABLED: bool = True
    OPS_LOG_MAX_BYTES: int = Field(default=5242880, ge=65536, le=52428800)
    OPS_LOG_BACKUP_COUNT: int = Field(default=3, ge=1, le=20)
    OPS_SLOW_REQUEST_SECONDS: float = Field(default=2, ge=0.1, le=120)
    OPS_RECENT_ERROR_THRESHOLD: int = Field(default=5, ge=1, le=100)
    OPS_MIN_FREE_BYTES: int = Field(default=536870912, ge=1048576)
    OPS_HEALTH_BASE_URL: str = "http://127.0.0.1:8000"

    @model_validator(mode="after")
    def production_cookie_policy(self):
        if self.ENVIRONMENT == "production":
            if not self.RATE_LIMIT_ENABLED:
                raise ValueError("Production requires RATE_LIMIT_ENABLED=true")
            if not self.COOKIE_SECURE or not self.ALLOWED_ORIGINS or any(not value.startswith("https://") or "*" in value for value in self.ALLOWED_ORIGINS):
                raise ValueError("Production requires COOKIE_SECURE=true and explicit HTTPS ALLOWED_ORIGINS")
        if self.PASSWORD_RECOVERY_ENABLED:
            if not self.SMTP_HOST or not self.SMTP_USERNAME or not self.SMTP_PASSWORD.get_secret_value():
                raise ValueError("Password recovery requires SMTP_HOST, SMTP_USERNAME and SMTP_PASSWORD")
            if not re.fullmatch(r"[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+", self.SMTP_FROM) or any(character in self.SMTP_FROM_NAME for character in "\r\n"):
                raise ValueError("Configure a valid SMTP_FROM address and sender name")
            base = urlsplit(self.RESET_BASE_URL)
            if base.scheme not in {"http", "https"} or not base.netloc or base.username or base.password or base.query or base.fragment:
                raise ValueError("RESET_BASE_URL must be a trusted frontend URL without credentials, query or fragment")
            if f"{base.scheme}://{base.netloc}" not in self.ALLOWED_ORIGINS:
                raise ValueError("RESET_BASE_URL must belong to an explicit ALLOWED_ORIGINS frontend")
            if self.ENVIRONMENT == "production" and base.scheme != "https":
                raise ValueError("Production reset links require HTTPS")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
