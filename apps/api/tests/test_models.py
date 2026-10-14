"""Tests for SQLAlchemy models structure and instantiation."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Business,
    Conversation,
    ConversationMode,
    Customer,
    Message,
    MessageRole,
    Order,
    Product,
    ToolCall,
    UsageLog,
    WhatsAppNumber,
)


@pytest.mark.anyio
async def test_business_instantiation(db_session: AsyncSession):
    """Verify Business model defaults and webhook generation on flush."""
    biz = Business(name="Acme Shoes")
    db_session.add(biz)
    await db_session.flush()

    assert biz.name == "Acme Shoes"
    assert len(biz.webhook_key) >= 32
    assert biz.history_limit == 20
    assert biz.ai_provider == "openai"
    assert biz.ai_model == "gpt-4o-mini"


@pytest.mark.anyio
async def test_models_uuid_and_enums(db_session: AsyncSession):
    """Verify enum values and UUID PK initialization on flush."""
    biz = Business(name="Enum Test")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+1122334455")
    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_123",
        access_token_enc="enc_tok",
        app_secret_enc="enc_sec",
        verify_token="v_tok",
    )
    db_session.add_all([cust, num])
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=num.id,
        mode=ConversationMode.BOT,
    )
    db_session.add(conv)
    await db_session.flush()

    assert conv.mode == ConversationMode.BOT
    assert conv.needs_human is False

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.CUSTOMER,
        body="Hello!",
    )
    db_session.add(msg)
    await db_session.flush()

    assert msg.role == MessageRole.CUSTOMER
    assert msg.type == "text"


@pytest.mark.anyio
async def test_product_and_order_models(db_session: AsyncSession):
    """Verify Product and Order models decimal types and attributes."""
    biz = Business(name="Shop Test")
    db_session.add(biz)
    await db_session.flush()

    prod = Product(
        business_id=biz.id,
        name="Sneakers",
        price=Decimal("99.99"),
        stock=10,
    )
    db_session.add(prod)
    await db_session.flush()

    assert prod.price == Decimal("99.99")
    assert prod.active is True

    order = Order(
        business_id=biz.id,
        customer_phone="+919876543210",
        total=Decimal("199.98"),
        status="confirmed",
    )
    db_session.add(order)
    await db_session.flush()

    assert order.customer_phone == "+919876543210"
    assert order.status == "confirmed"


def test_tool_call_and_usage_models():
    """Verify ToolCall and UsageLog structures."""
    conv_id = uuid.uuid4()
    tool_call = ToolCall(
        conversation_id=conv_id,
        tool="search_products",
        args={"query": "shoes"},
        ok=True,
    )
    assert tool_call.tool == "search_products"
    assert tool_call.args["query"] == "shoes"

    usage = UsageLog(
        conversation_id=conv_id,
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=150,
        output_tokens=30,
        latency_ms=420,
    )
    assert usage.input_tokens == 150
    assert usage.latency_ms == 420
