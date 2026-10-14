"""Tests for conversation memory loader and token-budget trimming."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Conversation, Message, MessageRole
from app.services.memory.loader import estimate_tokens, load_conversation_history


def test_estimate_tokens():
    """Token estimation character heuristic tests."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("hi") == 1
    # 40 chars ≈ 10 tokens
    assert estimate_tokens("a" * 40) == 10


@pytest.mark.anyio
async def test_load_conversation_history_chronological(db_session: AsyncSession):
    """Verify messages are mapped to standardized Msg objects in chronological order."""
    biz = Business(name="Mem Biz", webhook_key="mem_key")
    db_session.add(biz)
    await db_session.flush()

    conv = Conversation(business_id=biz.id, customer_id=biz.id, number_id=biz.id)
    db_session.add(conv)
    await db_session.flush()

    m1 = Message(conversation_id=conv.id, role=MessageRole.CUSTOMER, body="Hello!")
    m2 = Message(conversation_id=conv.id, role=MessageRole.BOT, body="Namaste! How can I help?")
    m3 = Message(conversation_id=conv.id, role=MessageRole.CUSTOMER, body="Do you have shoes?")
    db_session.add_all([m1, m2, m3])
    await db_session.commit()

    history = await load_conversation_history(db_session, conv.id, limit=10, max_tokens=1000)

    assert len(history) == 3
    assert history[0].role == "user"
    assert history[0].content == "Hello!"
    assert history[1].role == "assistant"
    assert history[1].content == "Namaste! How can I help?"
    assert history[2].role == "user"
    assert history[2].content == "Do you have shoes?"


@pytest.mark.anyio
async def test_load_conversation_history_token_trimming(db_session: AsyncSession):
    """Verify older messages are pruned when total tokens exceed max_tokens."""
    biz = Business(name="Trim Biz", webhook_key="trim_key")
    db_session.add(biz)
    await db_session.flush()

    conv = Conversation(business_id=biz.id, customer_id=biz.id, number_id=biz.id)
    db_session.add(conv)
    await db_session.flush()

    # 4 messages of ~100 characters each (≈ 25 tokens each)
    m1 = Message(
        conversation_id=conv.id, role=MessageRole.CUSTOMER, body="First old message " + "x" * 80
    )
    m2 = Message(
        conversation_id=conv.id, role=MessageRole.BOT, body="Second old response " + "y" * 80
    )
    m3 = Message(
        conversation_id=conv.id,
        role=MessageRole.CUSTOMER,
        body="Third recent question " + "z" * 80,
    )
    m4 = Message(
        conversation_id=conv.id,
        role=MessageRole.CUSTOMER,
        body="Fourth newest message " + "w" * 80,
    )
    db_session.add_all([m1, m2, m3, m4])
    await db_session.commit()

    # Budget of only ~55 tokens (should drop m1 and m2, keeping m3 and m4)
    history = await load_conversation_history(db_session, conv.id, limit=10, max_tokens=55)

    assert len(history) < 4
    # The newest message must always be preserved
    assert history[-1].content.startswith("Fourth newest message")


@pytest.mark.anyio
async def test_load_conversation_history_always_keeps_latest(db_session: AsyncSession):
    """Verify at least 1 newest message is retained even if it alone exceeds max_tokens."""
    biz = Business(name="Single Biz", webhook_key="single_key")
    db_session.add(biz)
    await db_session.flush()

    conv = Conversation(business_id=biz.id, customer_id=biz.id, number_id=biz.id)
    db_session.add(conv)
    await db_session.flush()

    # Huge message exceeding max_tokens
    m1 = Message(conversation_id=conv.id, role=MessageRole.CUSTOMER, body="A" * 2000)
    db_session.add(m1)
    await db_session.commit()

    history = await load_conversation_history(db_session, conv.id, limit=10, max_tokens=50)
    assert len(history) == 1
    assert len(history[0].content) == 2000
