"""Message repository."""

import uuid
from collections.abc import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole


class MessageRepository:
    """Repository for conversation messages."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_wa_message_id(self, wa_message_id: str) -> Message | None:
        """Find message by unique Meta WhatsApp message ID for deduplication."""
        query = select(Message).where(Message.wa_message_id == wa_message_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int = 50,
    ) -> Sequence[Message]:
        """Fetch latest messages in a conversation ordered chronologically."""
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        # Reverse to chronological order (oldest to newest)
        return list(reversed(result.scalars().all()))

    async def create(
        self,
        conversation_id: uuid.UUID,
        role: MessageRole,
        body: str,
        wa_message_id: str | None = None,
        type_: str = "text",
        status: str = "received",
    ) -> Message:
        """Create and persist a message."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            body=body,
            wa_message_id=wa_message_id,
            type=type_,
            status=status,
        )
        self.session.add(message)
        await self.session.flush()
        return message
