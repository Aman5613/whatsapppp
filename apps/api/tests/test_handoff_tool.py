"""Tests for handoff_to_human tool."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Conversation, ConversationMode
from app.tools.handoff_to_human import execute


@pytest.mark.anyio
async def test_handoff_tool_switches_mode_and_flag(db_session: AsyncSession):
    """Verify tool switches conversation mode to human and sets needs_human."""
    biz = Business(name="Handoff Test", webhook_key="h_key")
    db_session.add(biz)
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=biz.id,
        number_id=biz.id,
        mode=ConversationMode.BOT,
        needs_human=False,
    )
    db_session.add(conv)
    await db_session.commit()

    result = await execute(
        session=db_session,
        conversation=conv,
        args={"reason": "Customer angry about refund"},
    )

    assert result["status"] == "handoff_initiated"
    assert conv.mode == ConversationMode.HUMAN
    assert conv.needs_human is True
