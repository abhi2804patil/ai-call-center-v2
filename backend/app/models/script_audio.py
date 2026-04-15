import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScriptAudio(Base):
    __tablename__ = "script_audio_files"
    __table_args__ = (
        UniqueConstraint("script_id", "node_key", "language_code", name="uq_script_node_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    script_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False)
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(50), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[str] = mapped_column(String(500), nullable=False)
    audio_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    generation_cost_credits: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="generating")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    script = relationship("Script", back_populates="audio_files")
