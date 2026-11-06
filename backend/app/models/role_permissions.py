from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String, false, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class RolePermissions(Base):
    __tablename__ = "role_permissions"
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    quotations: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))
