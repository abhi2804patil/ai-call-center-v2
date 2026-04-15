import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    script_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    direction: Mapped[str] = mapped_column(String(20), default="outbound")
    schedule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=lambda: {"max_retries": 3, "retry_interval_minutes": 30, "concurrent_limit": 10})
    phone_list_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_numbers: Mapped[int] = mapped_column(Integer, default=0)
    called_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="campaigns")
    script = relationship("Script", back_populates="campaigns")
    call_logs = relationship("CallLog", back_populates="campaign")
    phone_numbers = relationship("PhoneNumber", back_populates="campaign", cascade="all, delete-orphan")
