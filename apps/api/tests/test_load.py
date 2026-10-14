"""Concurrent webhook burst test."""

import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.core.database import get_session
from app.main import app
from app.models import Business, WhatsAppNumber
from app.webhook import handlers as webhook_handlers
from scripts.load_test_webhook import build_webhook_payload, generate_signature


@pytest.mark.anyio
async def test_concurrent_webhook_burst(db_session: AsyncSession, monkeypatch):
    """Simulate a burst of 20 concurrent webhook posts and verify all succeed without deadlocks."""
    # Setup test business with whatsapp number
    biz = Business(name="Load Test Biz", webhook_key="burst_test_key")
    db_session.add(biz)
    await db_session.flush()

    raw_secret = "burst_secret_key_123"
    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="phone_load_1",
        access_token_enc=encrypt_value("test_tok"),
        app_secret_enc=encrypt_value(raw_secret),
        verify_token="test_verify_tok",
    )
    db_session.add(num)
    await db_session.commit()

    # Override get_session dependency
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    # Mock background task processing to test HTTP concurrency & handshake
    monkeypatch.setattr(webhook_handlers, "process_webhook_event", AsyncMock(return_value=None))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async def post_event(i: int):
            wa_id = f"wamid.burst_test_{int(time.time())}_{i}"
            payload = build_webhook_payload(
                wa_id=wa_id,
                sender_phone=f"+91980000{i:04d}",
                body_text=f"Concurrent message {i}",
            )
            body_bytes = json.dumps(payload).encode()
            sig = generate_signature(raw_secret, body_bytes)
            return await client.post(
                f"/webhook/{biz.webhook_key}",
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                },
            )

        # Run 20 concurrent requests
        responses = await asyncio.gather(*(post_event(i) for i in range(20)))

    app.dependency_overrides.clear()

    # All should return 200 OK
    assert all(r.status_code == 200 for r in responses)
