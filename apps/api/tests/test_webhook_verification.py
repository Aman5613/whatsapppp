"""Tests for GET /webhook/{webhook_key} Meta verification handshake."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.models import Business, WhatsAppNumber


@pytest.mark.anyio
async def test_webhook_verification_success(client, db_session: AsyncSession, monkeypatch):
    """Valid subscription handshake returns challenge with 200 OK."""
    biz = Business(name="Verify Biz", webhook_key="test_webhook_key_123")
    db_session.add(biz)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="10001",
        access_token_enc=encrypt_value("mock_tok"),
        app_secret_enc=encrypt_value("mock_sec"),
        verify_token="my_meta_verify_token",
    )
    db_session.add(number)
    await db_session.commit()

    # Override session dependency in app
    from app.core.database import get_session

    async def override_get_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_session] = override_get_session

    response = await client.get(
        f"/webhook/{biz.webhook_key}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my_meta_verify_token",
            "hub.challenge": "1158201444",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == "1158201444"


@pytest.mark.anyio
async def test_webhook_verification_wrong_token(client, db_session: AsyncSession):
    """Wrong verify token returns 403 Forbidden."""
    biz = Business(name="Verify Biz 2", webhook_key="test_webhook_key_456")
    db_session.add(biz)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="10002",
        access_token_enc=encrypt_value("mock_tok"),
        app_secret_enc=encrypt_value("mock_sec"),
        verify_token="correct_token",
    )
    db_session.add(number)
    await db_session.commit()

    from app.core.database import get_session

    async def override_get_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_session] = override_get_session

    response = await client.get(
        f"/webhook/{biz.webhook_key}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "1158201444",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.anyio
async def test_webhook_verification_unknown_business(client, db_session: AsyncSession):
    """Unknown webhook key returns 404."""
    from app.core.database import get_session

    async def override_get_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_session] = override_get_session

    response = await client.get(
        "/webhook/non_existent_key",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "tok",
            "hub.challenge": "1158201444",
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 404
