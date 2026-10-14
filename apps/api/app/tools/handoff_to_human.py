"""handoff_to_human tool definition and executor."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationMode
from app.services.ai.types import ToolSpec

SPEC = ToolSpec(
    name="handoff_to_human",
    description="Transfer the chat to a human agent/store owner when the customer requests human help or when their issue cannot be solved automatically.",
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Brief explanation why handoff was initiated (e.g. 'Customer asked for human', 'Complex exchange request')",
            },
        },
        "required": ["reason"],
    },
)


async def execute(
    session: AsyncSession,
    conversation: Conversation,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Switch conversation to human mode and set needs_human flag."""
    reason = args.get("reason", "Customer requested human assistance")

    conversation.mode = ConversationMode.HUMAN
    conversation.needs_human = True
    await session.flush()

    return {
        "status": "handoff_initiated",
        "reason": reason,
        "message": "Chat has been transferred to our human support team. A team member will reply shortly.",
    }
