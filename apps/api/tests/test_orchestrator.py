"""Tests for reply pipeline orchestrator, conversation locking, and usage tracking."""

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
    UsageLog,
    WhatsAppNumber,
)
from app.services.ai.types import LLMResult, StopReason, Usage
from app.services.pipeline.orchestrator import _FALLBACK_ERROR_MESSAGE, process_conversation_turn
from app.services.pipeline.rate_limit import customer_rate_limiter
from app.services.whatsapp.client import WhatsAppClient


class FakeProvider:
    """Mock LLMProvider for pipeline tests."""

    def __init__(
        self, reply_text: str = "Haan ji, size 9 available hai!", should_fail: bool = False
    ):
        self.provider_name = "mock_provider"
        self.model = "mock-v1"
        self.reply_text = reply_text
        self.should_fail = should_fail
        self.captured_messages = []

    async def generate(self, system: str, messages: list, tools=None) -> LLMResult:
        if self.should_fail:
            raise RuntimeError("API quota completely exhausted")
        self.captured_messages = messages
        return LLMResult(
            text=self.reply_text,
            usage=Usage(input_tokens=120, output_tokens=35),
            provider=self.provider_name,
            model=self.model,
            stop_reason=StopReason.END_TURN,
            latency_ms=350,
        )


@pytest.mark.anyio
async def test_orchestrator_multi_turn_reply_and_usage(db_session: AsyncSession, monkeypatch):
    """Verify orchestrator loads multi-turn history, sends reply, and logs token usage."""
    customer_rate_limiter.reset()

    biz = Business(
        name="Chai & Snacks Co.",
        system_prompt="We serve authentic snacks in Delhi.",
        ai_provider="openai",
        ai_model="gpt-4o-mini",
        ai_api_key_enc=encrypt_value("mock-ai-key"),
    )
    db_session.add(biz)
    await db_session.flush()

    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_orch_1",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="v_tok",
    )
    cust = Customer(business_id=biz.id, phone="919911223344", name="Aarav")
    db_session.add_all([num, cust])
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=num.id,
        mode=ConversationMode.BOT,
    )
    db_session.add(conv)
    await db_session.flush()

    # Pre-populate history (2 turns)
    m1 = Message(conversation_id=conv.id, role=MessageRole.CUSTOMER, body="Menu kya hai?")
    m2 = Message(
        conversation_id=conv.id, role=MessageRole.BOT, body="Humare paas Samosa aur Chai hai!"
    )
    db_session.add_all([m1, m2])
    await db_session.commit()

    fake_ai = FakeProvider(reply_text="Garam Samosa ready hai!")
    monkeypatch.setattr(
        "app.services.pipeline.orchestrator.get_providers_for_business",
        lambda b: (fake_ai, None),
    )

    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock(
        return_value={"messages": [{"id": "wamid.outbound_orch_999"}]}
    )

    # Execute conversation turn
    await process_conversation_turn(
        session=db_session,
        business=biz,
        number=num,
        customer=cust,
        conversation=conv,
        inbound_body="Samosa milega?",
        access_token="tok",
        client=mock_client,
    )

    # 1. Multi-turn history was supplied to LLM
    assert len(fake_ai.captured_messages) == 2
    assert fake_ai.captured_messages[0].content == "Menu kya hai?"

    # 2. WhatsApp send_text called with LLM reply
    mock_client.send_text.assert_called_once()
    call_args = mock_client.send_text.call_args[1]
    assert call_args["body"] == "Garam Samosa ready hai!"
    assert call_args["to"] == "919911223344"

    # 3. Outbound message stored in DB
    msg_res = await db_session.execute(
        select(Message).where(Message.wa_message_id == "wamid.outbound_orch_999")
    )
    saved_msg = msg_res.scalar_one_or_none()
    assert saved_msg is not None
    assert saved_msg.role == MessageRole.BOT
    assert saved_msg.body == "Garam Samosa ready hai!"

    # 4. UsageLog persisted
    usage_res = await db_session.execute(
        select(UsageLog).where(UsageLog.conversation_id == conv.id)
    )
    saved_usage = usage_res.scalar_one_or_none()
    assert saved_usage is not None
    assert saved_usage.input_tokens == 120
    assert saved_usage.output_tokens == 35
    assert saved_usage.provider == "mock_provider"


@pytest.mark.anyio
async def test_orchestrator_graceful_error_handling(db_session: AsyncSession, monkeypatch):
    """When LLM crashes, bot sends safe fallback message without failing."""
    customer_rate_limiter.reset()

    biz = Business(
        name="Error Biz",
        ai_provider="openai",
        ai_api_key_enc=encrypt_value("key"),
    )
    db_session.add(biz)
    await db_session.flush()

    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_err",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="v_tok",
    )
    cust = Customer(business_id=biz.id, phone="917766554433")
    db_session.add_all([num, cust])
    await db_session.flush()

    conv = Conversation(business_id=biz.id, customer_id=cust.id, number_id=num.id)
    db_session.add(conv)
    await db_session.commit()

    failing_ai = FakeProvider(should_fail=True)
    monkeypatch.setattr(
        "app.services.pipeline.orchestrator.get_providers_for_business",
        lambda b: (failing_ai, None),
    )

    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock(return_value={"messages": [{"id": "wamid.err_out"}]})

    await process_conversation_turn(
        session=db_session,
        business=biz,
        number=num,
        customer=cust,
        conversation=conv,
        inbound_body="Hello",
        access_token="tok",
        client=mock_client,
    )

    # Fallback message sent to customer
    call_args = mock_client.send_text.call_args[1]
    assert call_args["body"] == _FALLBACK_ERROR_MESSAGE


@pytest.mark.anyio
async def test_orchestrator_suppresses_in_human_mode(db_session: AsyncSession):
    """When conversation.mode is 'human', orchestrator exits without generating reply."""
    biz = Business(name="Human Biz")
    db_session.add(biz)
    await db_session.flush()

    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_h",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="v",
    )
    cust = Customer(business_id=biz.id, phone="919900000000")
    db_session.add_all([num, cust])
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=num.id,
        mode=ConversationMode.HUMAN,
    )
    db_session.add(conv)
    await db_session.commit()

    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock()

    await process_conversation_turn(
        session=db_session,
        business=biz,
        number=num,
        customer=cust,
        conversation=conv,
        inbound_body="Help",
        access_token="tok",
        client=mock_client,
    )

    # Nothing sent
    assert mock_client.send_text.call_count == 0
