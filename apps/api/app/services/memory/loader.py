"""Conversation memory loader with token-budget trimming."""

import logging
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole
from app.services.ai.types import Msg

logger = logging.getLogger(__name__)

# Heuristic: 1 token ≈ 4 characters
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str | None) -> int:
    """Estimate token count for a text string using character heuristic."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


async def load_conversation_history(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    limit: int = 20,
    max_tokens: int = 4000,
) -> list[Msg]:
    """Load recent messages for a conversation and trim to token budget.

    1. Fetches up to `limit` most recent messages ordered chronologically.
    2. Maps `customer` -> user, `bot` / `human` -> assistant.
    3. Trims oldest messages until total estimated tokens <= max_tokens.
    4. Guarantees that at least the most recent message is retained.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    # Reverse from newest-first to chronological (oldest-first)
    raw_messages = list(reversed(result.scalars().all()))

    if not raw_messages:
        return []

    # Map to standardized Msg objects
    converted: list[Msg] = []
    for m in raw_messages:
        role = "user" if m.role == MessageRole.CUSTOMER else "assistant"
        converted.append(Msg(role=role, content=m.body))

    # Token-budget trimming from the oldest messages
    total_tokens = sum(estimate_tokens(m.content) for m in converted)
    while len(converted) > 1 and total_tokens > max_tokens:
        dropped = converted.pop(0)
        total_tokens -= estimate_tokens(dropped.content)
        logger.debug(
            "Dropped oldest message to satisfy token budget (%d > %d)",
            total_tokens,
            max_tokens,
        )

    return converted
