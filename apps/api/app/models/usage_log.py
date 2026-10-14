"""AI token and latency usage log model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class UsageLog(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Log entry for LLM provider token consumption and request latency."""

    __tablename__ = "usage_log"
    __table_args__ = (
        Index("ix_usage_log_conversation_created", "conversation_id", "created_at"),
        Index("ix_usage_log_provider_model", "provider", "model"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="usage_logs"
    )
