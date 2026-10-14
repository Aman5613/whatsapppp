"""Tests for handoff intent heuristics and webhook triggering."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.models import Business, ConversationMode, WhatsAppNumber
from app.repositories import ConversationRepository
from app.services.handoff.triggers import detect_handoff_intent
from app.services.whatsapp.client import WhatsAppClient
from app.webhook.handlers import process_webhook_event


def test_detect_handoff_intent():
    # Should trigger
    assert detect_handoff_intent("I want to talk to a human") is True
    assert detect_handoff_intent("can I speak with an agent please?") is True
    assert detect_handoff_intent("Connect me to representative") is True
    assert detect_handoff_intent("need customer care") is True
    assert detect_handoff_intent("/human") is True
    assert detect_handoff_intent("/agent") is True
    assert detect_handoff_intent("kisi insan se baat karni hai") is True

    # Should NOT trigger
    assert detect_handoff_intent("What is the price of shoes?") is False
    assert detect_handoff_intent("Booking for 1 person") is False
    assert detect_handoff_intent("Where is my order?") is False
    assert detect_handoff_intent("") is False


@pytest.mark.anyio
async def test_webhook_inbound_handoff_trigger(db_session: AsyncSession, monkeypatch):
    """Verify inbound message with handoff intent switches mode and notifies customer."""
    biz = Business(name="Support Shop", webhook_key="support_key")
    db_session.add(biz)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="phone_support_1",
        access_token_enc=encrypt_value("mock_wa_token"),
        app_secret_enc=encrypt_value("mock_wa_secret"),
        verify_token="v_token",
    )
    db_session.add(number)
    await db_session.commit()

    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock(return_value={"messages": [{"id": "wamid.handoff_ack_1"}]})
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
                "id": "wa_acc_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "phone_support_1",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Alice Support"},
                                    "wa_id": "+919876543210",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "+919876543210",
                                    "id": "wamid.handoff_inbound_1",
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "I want to speak with an agent"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    await process_webhook_event(
        business_id=biz.id,
        payload_data=payload,
        client=mock_client,
    )

    conv_repo = ConversationRepository(db_session, business_id=biz.id)
    convs = await conv_repo.list_recent()
    assert len(convs) == 1
    conv = convs[0]

    assert conv.mode == ConversationMode.HUMAN
    assert conv.needs_human is True

    # Check that handoff ack message was sent
    mock_client.send_text.assert_called_once()
    assert "support team" in mock_client.send_text.call_args.kwargs["body"]
