"""WhatsApp Business Number credentials entity."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.conversation import Conversation


class WhatsAppNumber(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """WhatsApp Cloud API connection details for a business."""

    __tablename__ = "whatsapp_numbers"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_number_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    waba_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    app_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)
    verify_token: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="whatsapp_numbers")
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="number"
    )
