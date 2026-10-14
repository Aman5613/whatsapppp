"""Tests for usage analytics API endpoint."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.main import app
from app.models import (
    Business,
    Conversation,
    Customer,
    Message,
    MessageRole,
    UsageLog,
    WhatsAppNumber,
)


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.anyio
async def test_usage_analytics_aggregation(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
):
    biz = Business(name="Analytics Corp", webhook_key="an_key")
    db_session.add(biz)
    await db_session.flush()

    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_an",
        access_token_enc="",
        app_secret_enc="",
        verify_token="tok",
    )
    cust = Customer(business_id=biz.id, phone="+917000000001")
    db_session.add_all([num, cust])
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=num.id,
        last_customer_message_at=datetime.now(UTC),
    )
    db_session.add(conv)
    await db_session.flush()

    msg1 = Message(
        conversation_id=conv.id,
        role=MessageRole.CUSTOMER,
        body="Price of item?",
    )
    msg2 = Message(
        conversation_id=conv.id,
        role=MessageRole.BOT,
        body="It costs Rs. 500.",
    )
    db_session.add_all([msg1, msg2])
    await db_session.flush()

    log1 = UsageLog(
        conversation_id=conv.id,
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=150,
        output_tokens=40,
        latency_ms=250,
    )
    log2 = UsageLog(
        conversation_id=conv.id,
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=200,
        output_tokens=60,
        latency_ms=310,
    )
    db_session.add_all([log1, log2])
    await db_session.commit()

    resp = await client.get(f"/api/usage?business_id={biz.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_conversations"] == 1
    assert data["total_messages"] == 2
    assert data["total_ai_calls"] == 2
    assert data["total_input_tokens"] == 350
    assert data["total_output_tokens"] == 100
    assert data["total_tokens"] == 450
    assert data["total_estimated_cost"] > 0
    assert len(data["breakdown_by_model"]) == 1
    assert data["breakdown_by_model"][0]["model"] == "gpt-4o-mini"
    assert len(data["recent_logs"]) == 2
