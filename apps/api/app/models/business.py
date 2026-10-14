"""Business tenant model."""

import secrets
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.customer import Customer
    from app.models.order import Order
    from app.models.product import Product
    from app.models.user import User
    from app.models.whatsapp_number import WhatsAppNumber


def generate_webhook_key() -> str:
    """Generate a cryptographically secure random token for the business webhook URL."""
    return secrets.token_urlsafe(32)


class Business(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Business tenant entity."""

    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str] = mapped_column(
        Text,
        default="You are a helpful customer service assistant for this business.",
        nullable=False,
    )
    language_pref: Mapped[str] = mapped_column(String(50), default="hinglish", nullable=False)
    tone: Mapped[str] = mapped_column(
        String(50), default="friendly and professional", nullable=False
    )

    # Primary AI Provider settings
    ai_provider: Mapped[str] = mapped_column(String(50), default="openai", nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), default="gpt-4o-mini", nullable=False)
    ai_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Fallback AI Provider settings
    fallback_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fallback_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fallback_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Webhook key for routing incoming Meta events
    webhook_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        default=generate_webhook_key,
        nullable=False,
    )

    history_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    # Relationships
    whatsapp_numbers: Mapped[list["WhatsAppNumber"]] = relationship(
        "WhatsAppNumber", back_populates="business", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="business", cascade="all, delete-orphan"
    )
    customers: Mapped[list["Customer"]] = relationship(
        "Customer", back_populates="business", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="business", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="business", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="business", cascade="all, delete-orphan"
    )
