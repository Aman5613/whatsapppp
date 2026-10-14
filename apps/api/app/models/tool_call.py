"""Tool call audit log model."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class ToolCall(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Record of tool calls executed during AI response pipeline."""

    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("ix_tool_calls_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    args: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="tool_calls"
    )
