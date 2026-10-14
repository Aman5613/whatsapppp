"""Conversation thread model."""

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.customer import Customer
    from app.models.message import Message
    from app.models.tool_call import ToolCall
    from app.models.usage_log import UsageLog
    from app.models.whatsapp_number import WhatsAppNumber


class ConversationMode(enum.StrEnum):
    """Conversation handler mode."""

    BOT = "bot"
    HUMAN = "human"


class Conversation(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Chat thread between a customer and the business WhatsApp number."""

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_business_last_msg", "business_id", "last_customer_message_at"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_numbers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    mode: Mapped[ConversationMode] = mapped_column(
        Enum(ConversationMode, values_callable=lambda x: [e.value for e in x]),
        default=ConversationMode.BOT,
        nullable=False,
    )
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_customer_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="conversations")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="conversations")
    number: Mapped["WhatsAppNumber"] = relationship(
        "WhatsAppNumber", back_populates="conversations"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall", back_populates="conversation", cascade="all, delete-orphan"
    )
    usage_logs: Mapped[list["UsageLog"]] = relationship(
        "UsageLog", back_populates="conversation", cascade="all, delete-orphan"
    )
