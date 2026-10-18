"""Human handoff and operator messaging service."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_value
from app.models.conversation import Conversation, ConversationMode
from app.models.message import Message, MessageRole
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.window import is_within_service_window

logger = structlog.get_logger(__name__)


class ServiceWindowExpiredError(Exception):
    """Raised when trying to send a session message outside the 24-hour window."""


class ConversationNotFoundError(Exception):
    """Raised when conversation cannot be found or is not tenant-owned."""


class WhatsAppDeliveryError(Exception):
    """Raised when sending a message to Meta Graph API fails."""


async def transition_to_human(
    session: AsyncSession,
    conversation: Conversation,
    needs_human: bool = False,
) -> Conversation:
    """Transition conversation to human operator mode."""
    conversation.mode = ConversationMode.HUMAN
    conversation.needs_human = needs_human
    await session.flush()
    logger.info(
        "Transitioned conversation to human mode",
        conversation_id=str(conversation.id),
        needs_human=needs_human,
    )
    return conversation


async def transition_to_bot(
    session: AsyncSession,
    conversation: Conversation,
) -> Conversation:
    """Return conversation to AI bot mode."""
    conversation.mode = ConversationMode.BOT
    conversation.needs_human = False
    await session.flush()
    logger.info(
        "Returned conversation to bot mode",
        conversation_id=str(conversation.id),
    )
    return conversation


async def auto_return_inactive_conversations(
    session: AsyncSession,
    business_id: uuid.UUID,
    timeout_minutes: int = 60,
) -> list[uuid.UUID]:
    """Auto-return human-mode conversations to bot mode if inactive beyond timeout."""
    threshold = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    query = select(Conversation).where(
        Conversation.business_id == business_id,
        Conversation.mode == ConversationMode.HUMAN,
        Conversation.last_customer_message_at <= threshold,
    )
    result = await session.execute(query)
    conversations = result.scalars().all()

    returned_ids: list[uuid.UUID] = []
    for conv in conversations:
        conv.mode = ConversationMode.BOT
        conv.needs_human = False
        returned_ids.append(conv.id)

    if returned_ids:
        await session.flush()
        logger.info(
            "Auto-returned inactive conversations to bot mode",
            count=len(returned_ids),
            returned_ids=[str(i) for i in returned_ids],
            business_id=str(business_id),
        )

    return returned_ids


async def send_human_reply(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    business_id: uuid.UUID,
    body: str,
    client: WhatsAppClient | None = None,
) -> Message:
    """Send an outbound reply from a human operator to a WhatsApp customer."""
    conv_repo = ConversationRepository(session, business_id=business_id)
    conversation = await conv_repo.get_with_messages(conversation_id)

    if not conversation:
        raise ConversationNotFoundError(f"Conversation {conversation_id} not found.")

    # 1. 24-hour service window check
    if not is_within_service_window(conversation.last_customer_message_at):
        raise ServiceWindowExpiredError(
            "Customer is outside the 24-hour WhatsApp service window. "
            "Free-form session messages cannot be sent; template required."
        )

    # 2. WhatsApp dispatch
    wa_client = client or WhatsAppClient()
    access_token = None
    if conversation.number and conversation.number.access_token_enc:
        try:
            access_token = decrypt_value(conversation.number.access_token_enc)
        except Exception as exc:
            raise WhatsAppDeliveryError(
                "Failed to decrypt WhatsApp access token. Please re-enter credentials in Settings."
            ) from exc

    if not access_token or not conversation.number:
        raise WhatsAppDeliveryError(
            "WhatsApp credentials are not configured for this number. Please configure them in Settings."
        )

    wa_message_id: str | None = None
    if conversation.customer:
        try:
            resp = await wa_client.send_text(
                phone_number_id=conversation.number.phone_number_id,
                access_token=access_token,
                to=conversation.customer.phone,
                body=body,
            )
            messages_resp = resp.get("messages", [])
            if messages_resp:
                wa_message_id = messages_resp[0].get("id")
        except httpx.HTTPStatusError as exc:
            meta_msg = exc.response.text
            try:
                error_data = exc.response.json()
                if isinstance(error_data, dict) and "error" in error_data and "message" in error_data["error"]:
                    meta_msg = error_data["error"]["message"]
            except Exception:
                pass
            logger.error(
                "WhatsApp API delivery failure",
                status_code=exc.response.status_code,
                error=meta_msg,
            )
            raise WhatsAppDeliveryError(f"WhatsApp API error: {meta_msg}") from exc
        except Exception as exc:
            logger.error("WhatsApp delivery exception", error=str(exc))
            raise WhatsAppDeliveryError(f"Delivery failed: {exc}") from exc

    # 3. Persist outbound human message
    msg_repo = MessageRepository(session)
    message = await msg_repo.create(
        conversation_id=conversation.id,
        role=MessageRole.HUMAN,
        body=body,
        wa_message_id=wa_message_id,
        type_="text",
        status="sent",
    )

    # 4. Operator is active in this conversation
    conversation.mode = ConversationMode.HUMAN
    conversation.needs_human = False
    await session.flush()

    return message
