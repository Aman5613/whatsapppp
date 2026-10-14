"""WhatsApp Cloud API HTTP Client using httpx."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GRAPH_API_BASE_URL = "https://graph.facebook.com/v21.0"
_DEFAULT_TIMEOUT = 15.0  # seconds


class WhatsAppClient:
    """Client for Meta WhatsApp Cloud API."""

    def __init__(self, base_url: str = _GRAPH_API_BASE_URL, timeout: float = _DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    async def send_text(
        self,
        phone_number_id: str,
        access_token: str,
        to: str,
        body: str,
    ) -> dict[str, Any]:
        """Send a free-form text message to a customer's WhatsApp number."""
        # Ensure recipient phone has no '+' or whitespace
        recipient = to.strip().lstrip("+")
        url = f"{self.base_url}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": body,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            if not response.is_success:
                logger.error(
                    "WhatsApp send_text failed: status=%s body=%s",
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()
            return response.json()

    async def mark_as_read(
        self,
        phone_number_id: str,
        access_token: str,
        wa_message_id: str,
    ) -> bool:
        """Mark an incoming customer message as read."""
        url = f"{self.base_url}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": wa_message_id,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                return response.is_success
        except Exception as exc:
            logger.warning("Failed to mark message as read: %s", exc)
            return False
