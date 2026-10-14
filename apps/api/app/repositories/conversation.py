"""Conversation repository."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import desc, or_
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, ConversationMode
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Tenant-scoped conversation repository."""

    async def get_with_messages(self, conversation_id: uuid.UUID) -> Conversation | None:
        """Fetch conversation along with its customer, number, and messages."""
        query = (
            self._scoped_query()
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.customer),
                selectinload(Conversation.number),
                selectinload(Conversation.messages),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        customer_id: uuid.UUID,
        number_id: uuid.UUID,
    ) -> tuple[Conversation, bool]:
        """Get active conversation for customer or create a new one."""
        query = self._scoped_query().where(
            Conversation.customer_id == customer_id,
            Conversation.number_id == number_id,
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            return existing, False

        new_conv = Conversation(
            business_id=self.business_id,
            customer_id=customer_id,
            number_id=number_id,
            mode=ConversationMode.BOT,
            needs_human=False,
            last_customer_message_at=datetime.now(UTC),
        )
        self.session.add(new_conv)
        await self.session.flush()
        return new_conv, True

    async def list_recent(
        self,
        limit: int = 50,
        mode: ConversationMode | None = None,
        needs_human: bool | None = None,
    ) -> Sequence[Conversation]:
        """List conversations ordered by last customer message timestamp."""
        query = (
            self._scoped_query()
            .options(
                selectinload(Conversation.customer),
                selectinload(Conversation.messages),
            )
            .order_by(desc(Conversation.last_customer_message_at))
        )
        if mode is not None:
            query = query.where(Conversation.mode == mode)
        if needs_human is not None:
            query = query.where(Conversation.needs_human.is_(needs_human))

        query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_handoff_queue(self) -> Sequence[Conversation]:
        """List conversations needing human assistance or currently in human mode."""
        query = (
            self._scoped_query()
            .where(
                or_(
                    Conversation.needs_human.is_(True),
                    Conversation.mode == ConversationMode.HUMAN,
                )
            )
            .options(
                selectinload(Conversation.customer),
                selectinload(Conversation.messages),
            )
            .order_by(desc(Conversation.last_customer_message_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()
