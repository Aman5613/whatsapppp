"""Tests for background webhook message processing and deduplication."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.models import (
    Business,
    Conversation,
    ConversationMode,
    Customer,
    Message,
    MessageRole,
    WhatsAppNumber,
)
from app.services.whatsapp.client import WhatsAppClient
from app.webhook.handlers import process_webhook_event


@pytest.mark.anyio
async def test_webhook_processing_echo_and_deduplication(db_session: AsyncSession, monkeypatch):
    """Verify inbound message triggers echo and replay deduplication works."""
    biz = Business(name="Echo Shop", webhook_key="echo_key")
    db_session.add(biz)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="phone_echo_1",
        access_token_enc=encrypt_value("mock_wa_token"),
        app_secret_enc=encrypt_value("mock_wa_secret"),
        verify_token="v_token",
    )
    db_session.add(number)
    await db_session.commit()

    # Mock WhatsAppClient
    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock(
        return_value={"messages": [{"id": "wamid.outbound_echo_123"}]}
    )
    mock_client.mark_as_read = AsyncMock(return_value=True)

    # Monkeypatch async_session_factory in webhook handlers to use db_session
    class MockSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    import app.webhook.handlers

    monkeypatch.setattr(app.webhook.handlers, "async_session_factory", MockSessionFactory())

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_echo_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "phone_echo_1"},
                            "contacts": [{"wa_id": "919988776655", "profile": {"name": "Rohan"}}],
                            "messages": [
                                {
                                    "id": "wamid.inbound_first_msg",
                                    "from": "919988776655",
                                    "timestamp": "1720000000",
                                    "type": "text",
                                    "text": {"body": "Namaste, price kya hai?"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    # 1. First event delivery
    await process_webhook_event(biz.id, payload, client=mock_client)

    # Verify Customer created
    cust_res = await db_session.execute(
        select(Customer).where(Customer.phone == "919988776655", Customer.business_id == biz.id)
    )
    customer = cust_res.scalar_one_or_none()
    assert customer is not None
    assert customer.name == "Rohan"

    # Verify Conversation created
    conv_res = await db_session.execute(
        select(Conversation).where(Conversation.customer_id == customer.id)
    )
    conv = conv_res.scalar_one_or_none()
    assert conv is not None

    # Verify Inbound and Outbound Messages stored
    msgs_res = await db_session.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    )
    messages = msgs_res.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == MessageRole.CUSTOMER
    assert messages[0].body == "Namaste, price kya hai?"
    assert messages[1].role == MessageRole.BOT
    assert messages[1].body == "Echo: Namaste, price kya hai?"

    # Verify send_text called once
    assert mock_client.send_text.call_count == 1
    assert mock_client.mark_as_read.call_count == 1

    # 2. Replay same payload (Meta retry simulation)
    await process_webhook_event(biz.id, payload, client=mock_client)

    # Message count should STILL be 2 (no duplicate replies sent or stored)
    msgs_res_replay = await db_session.execute(
        select(Message).where(Message.conversation_id == conv.id)
    )
    assert len(msgs_res_replay.scalars().all()) == 2
    # send_text call count should still be 1!
    assert mock_client.send_text.call_count == 1


@pytest.mark.anyio
async def test_webhook_processing_skips_bot_reply_in_human_mode(
    db_session: AsyncSession, monkeypatch
):
    """When conversation.mode is 'human', bot reply is suppressed."""
    biz = Business(name="Human Mode Biz", webhook_key="human_key")
    db_session.add(biz)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="phone_human_1",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="v_tok",
    )
    cust = Customer(business_id=biz.id, phone="918888777766", name="Vikram")
    db_session.add_all([number, cust])
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=number.id,
        mode=ConversationMode.HUMAN,
        needs_human=True,
    )
    db_session.add(conv)
    await db_session.commit()

    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock()
    mock_client.mark_as_read = AsyncMock(return_value=True)

    class MockSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    import app.webhook.handlers

    monkeypatch.setattr(app.webhook.handlers, "async_session_factory", MockSessionFactory())

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_human",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "phone_human_1"},
                            "messages": [
                                {
                                    "id": "wamid.msg_human_mode",
                                    "from": "918888777766",
                                    "timestamp": "1720000000",
                                    "type": "text",
                                    "text": {"body": "I need help from agent"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    await process_webhook_event(biz.id, payload, client=mock_client)

    # Inbound message stored
    msg_res = await db_session.execute(
        select(Message).where(Message.wa_message_id == "wamid.msg_human_mode")
    )
    inbound_msg = msg_res.scalar_one_or_none()
    assert inbound_msg is not None

    # BUT bot echo was NOT sent!
    assert mock_client.send_text.call_count == 0


@pytest.mark.anyio
async def test_webhook_processing_status_callback(db_session: AsyncSession, monkeypatch):
    """Status updates (delivered, read) update existing message status."""
    biz = Business(name="Status Biz", webhook_key="status_key")
    db_session.add(biz)
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=biz.id,  # dummy for test
        number_id=biz.id,
    )
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.BOT,
        body="Order confirmed",
        wa_message_id="wamid.status_target_123",
        status="sent",
    )
    db_session.add(msg)
    await db_session.commit()

    class MockSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    import app.webhook.handlers

    monkeypatch.setattr(app.webhook.handlers, "async_session_factory", MockSessionFactory())

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_status",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "dummy_num"},
                            "statuses": [
                                {
                                    "id": "wamid.status_target_123",
                                    "status": "delivered",
                                    "timestamp": "1720000010",
                                    "recipient_id": "919988776655",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    await process_webhook_event(biz.id, payload)

    # Status should now be updated to 'delivered'
    updated_res = await db_session.execute(
        select(Message).where(Message.wa_message_id == "wamid.status_target_123")
    )
    updated_msg = updated_res.scalar_one_or_none()
    assert updated_msg is not None
    assert updated_msg.status == "delivered"
