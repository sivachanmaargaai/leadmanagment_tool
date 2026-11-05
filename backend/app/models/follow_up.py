import uuid
from datetime import datetime, timezone

from sqlalchemy import Index, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class FollowUp(Base):
    __tablename__ = "follow_ups"
    __table_args__ = (Index("ix_follow_ups_list_order", "due_at", "id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id: Mapped[str] = mapped_column(String(36), ForeignKey("leads.id", ondelete="RESTRICT"), index=True)
    purpose: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="Call")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    assigned_to: Mapped[str] = mapped_column(String(100), default="Admin")
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=30)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Pending", index=True)
    outcome: Mapped[str] = mapped_column(String(40), default="")
    completion_notes: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
