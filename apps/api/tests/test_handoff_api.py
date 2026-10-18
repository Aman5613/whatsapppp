"""Tests for handoff queue and conversation API endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.core.database import get_session
from app.main import app
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


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.anyio
async def test_handoff_queue_api(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
):
    biz = Business(name="Queue Shop", webhook_key="q_key")
    db_session.add(biz)
    await db_session.flush()

    cust1 = Customer(business_id=biz.id, phone="+919000000001", name="Alice Q")
    cust2 = Customer(business_id=biz.id, phone="+919000000002", name="Bob Q")
    db_session.add_all([cust1, cust2])
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_q",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    # Conv 1: needs_human=True
    conv1 = Conversation(
        business_id=biz.id,
        customer_id=cust1.id,
        number_id=number.id,
        mode=ConversationMode.HUMAN,
        needs_human=True,
        last_customer_message_at=datetime.now(UTC),
    )
    # Conv 2: normal bot conversation
    conv2 = Conversation(
        business_id=biz.id,
        customer_id=cust2.id,
        number_id=number.id,
        mode=ConversationMode.BOT,
        needs_human=False,
        last_customer_message_at=datetime.now(UTC),
    )
    db_session.add_all([conv1, conv2])
    await db_session.flush()

    # Add message to conv1
    msg1 = Message(
        conversation_id=conv1.id,
        role=MessageRole.CUSTOMER,
        body="I need a person!",
    )
    db_session.add(msg1)
    await db_session.commit()

    resp = await client.get(f"/api/handoff?business_id={biz.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 1
    assert data[0]["conversation_id"] == str(conv1.id)
    assert data[0]["customer_name"] == "Alice Q"
    assert data[0]["last_message_body"] == "I need a person!"
    assert data[0]["needs_human"] is True


@pytest.mark.anyio
async def test_conversation_detail_and_takeover_api(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
):
    biz = Business(name="Takeover Shop", webhook_key="to_key")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+919000000003", name="Charlie T")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_to",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=number.id,
        mode=ConversationMode.BOT,
        needs_human=True,
        last_customer_message_at=datetime.now(UTC),
    )
    db_session.add(conv)
    await db_session.commit()

    # 1. Take over conversation
    takeover_resp = await client.post(
        f"/api/conversations/{conv.id}/take-over?business_id={biz.id}"
    )
    assert takeover_resp.status_code == 200
    assert takeover_resp.json()["mode"] == "human"
    assert takeover_resp.json()["needs_human"] is False

    # 2. Get conversation detail
    detail_resp = await client.get(f"/api/conversations/{conv.id}?business_id={biz.id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == str(conv.id)
    assert detail["mode"] == "human"
    assert detail["customer_name"] == "Charlie T"

    # 3. Return to bot
    return_resp = await client.post(
        f"/api/conversations/{conv.id}/return-to-bot?business_id={biz.id}"
    )
    assert return_resp.status_code == 200
    assert return_resp.json()["mode"] == "bot"
    assert return_resp.json()["needs_human"] is False


@pytest.mark.anyio
async def test_post_operator_message_api(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    biz = Business(name="Operator Reply Shop", webhook_key="op_key")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+919000000004", name="Diana")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_op",
        access_token_enc=encrypt_value("mock_op_token"),
        app_secret_enc=encrypt_value("sec"),
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

    # Mock WhatsAppClient
    mock_send = AsyncMock(return_value={"messages": [{"id": "wamid.api_operator_123"}]})
    monkeypatch.setattr(WhatsAppClient, "send_text", mock_send)

    resp = await client.post(
        f"/api/conversations/{conv.id}/messages?business_id={biz.id}",
        json={"body": "Hello Diana, I'm taking care of your request."},
    )
    assert resp.status_code == 200
    msg = resp.json()
    assert msg["role"] == "human"
    assert msg["body"] == "Hello Diana, I'm taking care of your request."
    assert msg["wa_message_id"] == "wamid.api_operator_123"

    mock_send.assert_called_once()


@pytest.mark.anyio
async def test_post_operator_message_outside_24h_returns_400(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
):
    biz = Business(name="Old Chat Shop", webhook_key="old_key")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+919000000005")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_old",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("sec"),
        verify_token="tok",
    )
    db_session.add(number)
    await db_session.flush()

    expired_time = datetime.now(UTC) - timedelta(hours=26)
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

    resp = await client.post(
        f"/api/conversations/{conv.id}/messages?business_id={biz.id}",
        json={"body": "This message should be rejected due to 24h window."},
    )
    assert resp.status_code == 400
    assert "24-hour" in resp.json()["detail"]


@pytest.mark.anyio
async def test_post_operator_message_whatsapp_rejection_returns_400(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """Verify that Meta Graph API errors return clean 400 instead of 500."""
    biz = Business(name="Meta Err Shop", webhook_key="err_key")
    db_session.add(biz)
    await db_session.flush()

    cust = Customer(business_id=biz.id, phone="+919000000006")
    db_session.add(cust)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_err",
        access_token_enc=encrypt_value("expired_tok"),
        app_secret_enc=encrypt_value("sec"),
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

    # Simulate Meta Graph API HTTP 400 error
    async def mock_send_text_fail(*args, **kwargs):
        req = httpx.Request("POST", "https://graph.facebook.com/v21.0/messages")
        res = httpx.Response(
            status_code=400,
            json={"error": {"message": "Error validating access token: Session has expired", "code": 190}},
            request=req,
        )
        raise httpx.HTTPStatusError("Bad Request", request=req, response=res)

    monkeypatch.setattr(WhatsAppClient, "send_text", mock_send_text_fail)

    resp = await client.post(
        f"/api/conversations/{conv.id}/messages?business_id={biz.id}",
        json={"body": "Should fail gracefully"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert "WhatsApp API error" in data["detail"]
    assert "Session has expired" in data["detail"]


@pytest.mark.anyio
async def test_event_broadcaster():
    """Verify in-memory event pub/sub broadcaster dispatches events to subscribers."""
    from app.core.events import broadcaster

    biz_id = str(uuid.uuid4())
    queue = broadcaster.subscribe(biz_id)
    try:
        await broadcaster.broadcast(biz_id, "new_message", {"conversation_id": "c1", "body": "hello"})
        item = queue.get_nowait()
        assert item["type"] == "new_message"
        assert item["data"]["body"] == "hello"
    finally:
        broadcaster.unsubscribe(biz_id, queue)

