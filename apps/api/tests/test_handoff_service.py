"""Tests for handoff service functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.models import (
    Business,
    Conversation,
    ConversationMode,
    Customer,
    MessageRole,
    WhatsAppNumber,
)
from app.services.handoff.service import (
    ConversationNotFoundError,
    ServiceWindowExpiredError,
    auto_return_inactive_conversations,
    send_human_reply,
    transition_to_bot,
    transition_to_human,
)
from app.services.whatsapp.client import WhatsAppClient


@pytest.mark.anyio
async def test_handoff_transitions(db_session: AsyncSession):
    biz = Business(name="Transitions Co", webhook_key="trans_key")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+919999999999", name="Test Customer")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_123",
        access_token_enc=encrypt_value("test_tok"),
        app_secret_enc=encrypt_value("test_sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=number.id,
        mode=ConversationMode.BOT,
        needs_human=False,
        last_customer_message_at=datetime.now(UTC),
    )
    db_session.add(conv)
    await db_session.commit()

    # 1. Transition to human
    await transition_to_human(db_session, conv, needs_human=True)
    assert conv.mode == ConversationMode.HUMAN
    assert conv.needs_human is True

    # 2. Operator takes over
    await transition_to_human(db_session, conv, needs_human=False)
    assert conv.mode == ConversationMode.HUMAN
    assert conv.needs_human is False

    # 3. Return to bot
    await transition_to_bot(db_session, conv)
    assert conv.mode == ConversationMode.BOT
    assert conv.needs_human is False


@pytest.mark.anyio
async def test_auto_return_inactive_conversations(db_session: AsyncSession):
    biz = Business(name="Auto Return Co", webhook_key="auto_key")
    db_session.add(biz)
    await db_session.flush()

    cust1 = Customer(business_id=biz.id, phone="+911111111111")
    cust2 = Customer(business_id=biz.id, phone="+912222222222")
    db_session.add_all([cust1, cust2])
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_auto",
        access_token_enc=encrypt_value("test_tok"),
        app_secret_enc=encrypt_value("test_sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    # Conv 1: inactive for 90 minutes in HUMAN mode
    old_time = datetime.now(UTC) - timedelta(minutes=90)
    conv_inactive = Conversation(
        business_id=biz.id,
        customer_id=cust1.id,
        number_id=number.id,
        mode=ConversationMode.HUMAN,
        needs_human=True,
        last_customer_message_at=old_time,
    )

    # Conv 2: active 10 minutes ago in HUMAN mode
    recent_time = datetime.now(UTC) - timedelta(minutes=10)
    conv_active = Conversation(
        business_id=biz.id,
        customer_id=cust2.id,
        number_id=number.id,
        mode=ConversationMode.HUMAN,
        needs_human=True,
        last_customer_message_at=recent_time,
    )
    db_session.add_all([conv_inactive, conv_active])
    await db_session.commit()

    returned_ids = await auto_return_inactive_conversations(
        session=db_session,
        business_id=biz.id,
        timeout_minutes=60,
    )
    await db_session.commit()

    assert conv_inactive.id in returned_ids
    assert conv_active.id not in returned_ids

    await db_session.refresh(conv_inactive)
    await db_session.refresh(conv_active)

    assert conv_inactive.mode == ConversationMode.BOT
    assert conv_inactive.needs_human is False
    assert conv_active.mode == ConversationMode.HUMAN
    assert conv_active.needs_human is True


@pytest.mark.anyio
async def test_send_human_reply(db_session: AsyncSession):
    biz = Business(name="Human Reply Co", webhook_key="reply_key")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+918888888888")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_reply",
        access_token_enc=encrypt_value("valid_token"),
        app_secret_enc=encrypt_value("test_sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=number.id,
        mode=ConversationMode.HUMAN,
        needs_human=True,
        last_customer_message_at=datetime.now(UTC),
    )
    db_session.add(conv)
    await db_session.commit()

    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock(
        return_value={"messages": [{"id": "wamid.operator_msg_999"}]}
    )

    msg = await send_human_reply(
        session=db_session,
        conversation_id=conv.id,
        business_id=biz.id,
        body="Hello from customer support agent!",
        client=mock_client,
    )
    await db_session.commit()

    assert msg.role == MessageRole.HUMAN
    assert msg.body == "Hello from customer support agent!"
    assert msg.wa_message_id == "wamid.operator_msg_999"
    assert msg.status == "sent"

    mock_client.send_text.assert_called_once_with(
        phone_number_id="num_reply",
        access_token="valid_token",
        to="+918888888888",
        body="Hello from customer support agent!",
    )


@pytest.mark.anyio
async def test_send_human_reply_service_window_expired(db_session: AsyncSession):
    biz = Business(name="Expired Window Co", webhook_key="exp_key")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+917777777777")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_exp",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    # Expired > 24 hours ago
    expired_time = datetime.now(UTC) - timedelta(hours=25)
    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=number.id,
        mode=ConversationMode.HUMAN,
        needs_human=True,
        last_customer_message_at=expired_time,
    )
    db_session.add(conv)
    await db_session.commit()

    with pytest.raises(ServiceWindowExpiredError):
        await send_human_reply(
            session=db_session,
            conversation_id=conv.id,
            business_id=biz.id,
            body="Should fail due to 24h window",
        )


@pytest.mark.anyio
async def test_send_human_reply_tenant_isolation(db_session: AsyncSession):
    biz_a = Business(name="Biz A", webhook_key="a_key")
    biz_b = Business(name="Biz B", webhook_key="b_key")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    cust = Customer(business_id=biz_a.id, phone="+915555555555")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz_a.id,
        phone_number_id="num_a",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    conv_a = Conversation(
        business_id=biz_a.id,
        customer_id=cust.id,
        number_id=number.id,
        mode=ConversationMode.HUMAN,
        needs_human=True,
        last_customer_message_at=datetime.now(UTC),
    )
    db_session.add(conv_a)
    await db_session.commit()

    # Biz B trying to send message in Biz A's conversation must raise ConversationNotFoundError
    with pytest.raises(ConversationNotFoundError):
        await send_human_reply(
            session=db_session,
            conversation_id=conv_a.id,
            business_id=biz_b.id,
            body="Cross tenant hack attempt",
        )
