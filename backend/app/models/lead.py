import uuid
from datetime import datetime, timezone

from sqlalchemy import Integer, Index, ForeignKey, DateTime, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_list_order", "created_at", "id"),)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id", ondelete="RESTRICT", name="fk_leads_customer"), nullable=True, index=True)
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT", name="fk_leads_assignee"), nullable=True, index=True)


    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    customer: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    contact: Mapped[str] = mapped_column(
        String(150), default=""
    )

    division: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="New"
    )

    priority: Mapped[str] = mapped_column(
        String(20), default="Medium"
    )

    lead_source: Mapped[str] = mapped_column(
        "lead_source", String(100),
        default="Direct Enquiry"
    )

    referred_by: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )

    reference_notes: Mapped[str] = mapped_column(
        Text, default=""
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )