"""Integration test for full multi-turn tool calling loop in orchestrator."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.models import (
    Business,
    Conversation,
    Customer,
    Message,
    MessageRole,
    Product,
    ToolCall,
    WhatsAppNumber,
)
from app.services.ai.types import LLMResult, StopReason, Usage
from app.services.ai.types import ToolCall as AIToolCall
from app.services.pipeline.orchestrator import process_conversation_turn
from app.services.pipeline.rate_limit import customer_rate_limiter
from app.services.whatsapp.client import WhatsAppClient


class ToolCallingMockAI:
    """Mock provider simulating tool call on turn 1 and factual reply on turn 2."""

    def __init__(self):
        self.provider_name = "mock_ai"
        self.model = "mock-model"
        self.turn = 0

    async def generate(self, system: str, messages: list, tools=None) -> LLMResult:
        self.turn += 1
        if self.turn == 1:
            # LLM decides to call search_products tool
            return LLMResult(
                text=None,
                tool_calls=[
                    AIToolCall(
                        id="call_prod_123",
                        name="search_products",
                        arguments={"query": "Red sneakers size 9"},
                    )
                ],
                usage=Usage(input_tokens=100, output_tokens=30),
                provider=self.provider_name,
                model=self.model,
                stop_reason=StopReason.TOOL_USE,
            )
        else:
            # LLM inspects tool output and formulates answer based strictly on facts
            return LLMResult(
                text="Haan ji! Red sneakers size 9 available hain, 4 pairs stock me hain at Rs. 2499.",
                tool_calls=[],
                usage=Usage(input_tokens=150, output_tokens=40),
                provider=self.provider_name,
                model=self.model,
                stop_reason=StopReason.END_TURN,
            )


@pytest.mark.anyio
async def test_tool_loop_real_stock_reply(db_session: AsyncSession, monkeypatch):
    """'Red sneakers size 9 hai?' triggers tool lookup, checks real DB, and answers with stock."""
    customer_rate_limiter.reset()

    biz = Business(
        name="Sneaker Hub",
        system_prompt="Answer from tools only.",
        ai_provider="openai",
        ai_api_key_enc=encrypt_value("key"),
    )
    db_session.add(biz)
    await db_session.flush()

    # Seed product with real stock in database
    product = Product(
        business_id=biz.id,
        name="Red sneakers size 9",
        description="Comfortable red sport sneakers in UK size 9",
        category="Footwear",
        price=Decimal("2499.00"),
        stock=4,
        active=True,
    )
    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_sneaker",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="v_tok",
    )
    cust = Customer(business_id=biz.id, phone="919876500000", name="Kunal")
    db_session.add_all([product, num, cust])
    await db_session.flush()

    conv = Conversation(business_id=biz.id, customer_id=cust.id, number_id=num.id)
    db_session.add(conv)
    await db_session.commit()

    mock_ai = ToolCallingMockAI()
    monkeypatch.setattr(
        "app.services.pipeline.orchestrator.get_providers_for_business",
        lambda b: (mock_ai, None),
    )

    mock_client = WhatsAppClient()
    mock_client.send_text = AsyncMock(return_value={"messages": [{"id": "wamid.tool_loop_out"}]})

    # Run pipeline turn with incoming question
    await process_conversation_turn(
        session=db_session,
        business=biz,
        number=num,
        customer=cust,
        conversation=conv,
        inbound_body="Red sneakers size 9 hai?",
        access_token="tok",
        client=mock_client,
    )

    # 1. Verify 2 turns occurred (Tool call -> Tool result -> Text)
    assert mock_ai.turn == 2

    # 2. Verify tool_calls audit table has recorded the execution
    tc_res = await db_session.execute(select(ToolCall).where(ToolCall.conversation_id == conv.id))
    tool_calls = tc_res.scalars().all()
    assert len(tool_calls) == 1
    assert tool_calls[0].tool == "search_products"
    assert tool_calls[0].ok is True
    assert tool_calls[0].result["found"] is True
    assert tool_calls[0].result["products"][0]["stock"] == 4

    # 3. Verify outbound message sent and saved with factual answer
    mock_client.send_text.assert_called_once()
    sent_text = mock_client.send_text.call_args[1]["body"]
    assert "4 pairs" in sent_text

    msg_res = await db_session.execute(
        select(Message).where(Message.wa_message_id == "wamid.tool_loop_out")
    )
    saved_msg = msg_res.scalar_one_or_none()
    assert saved_msg is not None
    assert saved_msg.role == MessageRole.BOT
    assert "Red sneakers size 9 available hain" in saved_msg.body
