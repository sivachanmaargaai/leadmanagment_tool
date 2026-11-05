
import uuid
from datetime import datetime, timezone

from sqlalchemy import Integer, Index, ForeignKey, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_list_order", "created_at", "id"),)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT", name="fk_customers_assignee"), nullable=True, index=True)


    # Unique Customer ID
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Basic customer information
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Company",
    )

    # Associated divisions
    divisions: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Multiple contact persons
    contacts: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Address information
    address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    postcode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="",
    )

    gst: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="",
    )

    # Responsible employee
    assigned_to: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Admin",
    )

    # Additional notes
    notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # Lead source and referral details
    lead_source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
    )

    referred_by: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    reference_notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # Previous company names
    aliases: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Customer activity history
    history: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
