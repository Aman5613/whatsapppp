"""User account model for dashboard authentication."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUID7PrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.business import Business


class User(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Business owner or staff user."""

    __tablename__ = "users"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationship
    business: Mapped["Business"] = relationship("Business", back_populates="users")
