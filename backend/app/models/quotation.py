import uuid
from datetime import datetime, timezone

from sqlalchemy import Index, DateTime, ForeignKey, Integer, JSON, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Quotation(Base):
    __tablename__ = "quotations"
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id", ondelete="RESTRICT", name="fk_quotations_customer"), nullable=True, index=True)
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="RESTRICT", name="fk_quotations_assignee"), nullable=True, index=True)

    __table_args__ = (UniqueConstraint("division", "number_key", name="uq_quotation_division_number"), Index("ix_quotations_list_order", "created_at", "id"))

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    number: Mapped[str] = mapped_column(String(50))
    number_key: Mapped[str] = mapped_column(String(50))
    division: Mapped[str] = mapped_column(String(100))
    customer: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    source: Mapped[str] = mapped_column(String(20))
    document: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuotationFile(Base):
    __tablename__ = "quotation_files"
    __table_args__ = (UniqueConstraint("quotation_id", "revision", name="uq_quotation_file_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    quotation_id: Mapped[str] = mapped_column(String(36), ForeignKey("quotations.id", ondelete="RESTRICT"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(180))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    # Keep PDF data out of list/metadata queries; load only through PDF endpoints.
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
