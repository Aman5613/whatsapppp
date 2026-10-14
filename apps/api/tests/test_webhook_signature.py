"""Tests for X-Hub-Signature-256 signature verification."""

import hashlib
import hmac
import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.models import Business, WhatsAppNumber
from app.webhook.signature import verify_signature


def test_verify_signature_valid():
    """Valid HMAC signature returns True."""
    secret = "my_meta_app_secret_abc123"
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    computed_hash = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    header = f"sha256={computed_hash}"

    assert verify_signature(body, header, secret) is True


def test_verify_signature_tampered_body():
    """Tampered body returns False."""
    secret = "my_meta_app_secret_abc123"
    body = b'{"object":"whatsapp_business_account"}'
    computed_hash = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    header = f"sha256={computed_hash}"

    tampered_body = b'{"object":"tampered"}'
    assert verify_signature(tampered_body, header, secret) is False


def test_verify_signature_wrong_secret():
    """Wrong secret returns False."""
    body = b'{"test": 1}'
    computed_hash = hmac.new(b"secret_one", body, hashlib.sha256).hexdigest()
    header = f"sha256={computed_hash}"

    assert verify_signature(body, header, "secret_two") is False


def test_verify_signature_malformed_header():
    """Malformed signature header returns False."""
    assert verify_signature(b"data", "not_sha256", "secret") is False
    assert verify_signature(b"data", None, "secret") is False


@pytest.mark.anyio
async def test_webhook_post_rejects_bad_signature(client, db_session: AsyncSession):
    """POST /webhook/{key} with invalid signature returns 403 Forbidden."""
    biz = Business(name="Sig Biz", webhook_key="sig_test_key")
    db_session.add(biz)
    await db_session.flush()

    number = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="999888",
        access_token_enc=encrypt_value("tok"),
        app_secret_enc=encrypt_value("correct_app_secret"),
        verify_token="v_tok",
    )
    db_session.add(number)
    await db_session.commit()

    from app.core.database import get_session

    async def override_get_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_session] = override_get_session

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "999888"},
                            "messages": [],
                        },
                    }
                ],
            }
        ],
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # Send with bad signature
    response = await client.post(
        f"/webhook/{biz.webhook_key}",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=badbadbad000111222333444555666777888999aaabbbcccdddeeefff0001112",
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 403
