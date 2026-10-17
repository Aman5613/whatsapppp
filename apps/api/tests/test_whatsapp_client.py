"""Tests for WhatsApp client and 24-hour service window utility."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.window import is_within_service_window


def test_service_window_within_24h():
    """Timestamp within 24 hours returns True."""
    now = datetime.now(UTC)
    recent = now - timedelta(hours=2)
    assert is_within_service_window(recent) is True

    boundary = now - timedelta(hours=23, minutes=59)
    assert is_within_service_window(boundary) is True


def test_service_window_outside_24h():
    """Timestamp older than 24 hours returns False."""
    now = datetime.now(UTC)
    expired = now - timedelta(hours=24, minutes=1)
    assert is_within_service_window(expired) is False

    ancient = now - timedelta(days=7)
    assert is_within_service_window(ancient) is False

    assert is_within_service_window(None) is False


@pytest.mark.anyio
async def test_whatsapp_client_send_text(monkeypatch):
    """Verify send_text issues correct POST request to Meta Graph API."""
    captured_request = {}

    async def mock_post(self, url, json=None, headers=None):
        captured_request["url"] = str(url)
        captured_request["json"] = json
        captured_request["headers"] = headers
        return httpx.Response(
            200,
            json={"messaging_product": "whatsapp", "messages": [{"id": "wamid.outbound123"}]},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = WhatsAppClient(base_url="https://graph.facebook.com/v21.0")
    result = await client.send_text(
        phone_number_id="1234567890",
        access_token="test_access_token",
        to="+919876543210",
        body="Hello Customer",
    )

    assert result["messages"][0]["id"] == "wamid.outbound123"
    assert captured_request["url"] == "https://graph.facebook.com/v21.0/1234567890/messages"
    assert captured_request["headers"]["Authorization"] == "Bearer test_access_token"
    assert captured_request["json"]["to"] == "919876543210"
    assert captured_request["json"]["text"]["body"] == "Hello Customer"


@pytest.mark.anyio
async def test_whatsapp_client_mark_as_read(monkeypatch):
    """Verify mark_as_read issues status=read payload."""
    captured_request = {}

    async def mock_post(self, url, json=None, headers=None):
        captured_request["json"] = json
        return httpx.Response(
            200,
            json={"success": True},
            request=httpx.Request("POST", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = WhatsAppClient()
    success = await client.mark_as_read(
        phone_number_id="1234567890",
        access_token="tok",
        wa_message_id="wamid.inbound999",
    )
    assert success is True
    assert captured_request["json"]["status"] == "read"
    assert captured_request["json"]["message_id"] == "wamid.inbound999"


@pytest.mark.anyio
async def test_whatsapp_client_get_phone_number_info(monkeypatch):
    """Verify get_phone_number_info queries correct Graph API endpoint."""
    captured_request = {}

    async def mock_get(self, url, headers=None):
        captured_request["url"] = str(url)
        captured_request["headers"] = headers
        return httpx.Response(
            200,
            json={
                "verified_name": "Test Store",
                "display_phone_number": "+1 555-0100",
                "id": "1234567890",
                "quality_rating": "GREEN",
            },
            request=httpx.Request("GET", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    client = WhatsAppClient()
    info = await client.get_phone_number_info(
        phone_number_id="1234567890",
        access_token="test_token_abc",
    )
    assert info["verified_name"] == "Test Store"
    assert captured_request["url"] == "https://graph.facebook.com/v21.0/1234567890"
    assert captured_request["headers"]["Authorization"] == "Bearer test_token_abc"

