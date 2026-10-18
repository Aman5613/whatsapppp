"""Background processing handlers for WhatsApp webhook events."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.crypto import decrypt_value
from app.core.database import async_session_factory
from app.core.events import broadcaster
from app.models.business import Business
from app.models.conversation import ConversationMode
from app.models.message import MessageRole
from app.models.whatsapp_number import WhatsAppNumber
from app.repositories import ConversationRepository, CustomerRepository, MessageRepository
from app.services.handoff.triggers import detect_handoff_intent
from app.services.pipeline.orchestrator import process_conversation_turn
from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.models import WebhookPayload
from app.services.whatsapp.window import is_within_service_window

logger = logging.getLogger(__name__)


async def process_webhook_event(
    business_id: uuid.UUID,
    payload_data: dict[str, Any],
    client: WhatsAppClient | None = None,
) -> None:
    """Process inbound Meta webhook event in background."""
    client = client or WhatsAppClient()

    try:
        payload = WebhookPayload.model_validate(payload_data)
    except Exception as exc:
        logger.error("Failed to parse webhook payload: %s", exc)
        return

    async with async_session_factory() as session:
        try:
            # Load Business
            biz_query = select(Business).where(Business.id == business_id)
            biz_result = await session.execute(biz_query)
            business = biz_result.scalar_one_or_none()
            if not business:
                logger.warning("Business not found for ID: %s", business_id)
                return

            cust_repo = CustomerRepository(session, business.id)
            conv_repo = ConversationRepository(session, business.id)
            msg_repo = MessageRepository(session)

            for entry in payload.entry:
                for change in entry.changes:
                    value = change.value
                    phone_number_id = value.metadata.phone_number_id

                    # --- Process Status Callbacks ---
                    for status_item in value.statuses:
                        status_msg = await msg_repo.get_by_wa_message_id(status_item.id)
                        if status_msg:
                            status_msg.status = status_item.status
                            await session.flush()

                    # Look up WhatsAppNumber entity for inbound messages
                    if not value.messages:
                        continue

                    num_query = select(WhatsAppNumber).where(
                        WhatsAppNumber.phone_number_id == phone_number_id,
                        WhatsAppNumber.business_id == business.id,
                    )
                    num_result = await session.execute(num_query)
                    number = num_result.scalar_one_or_none()
                    if not number:
                        logger.warning(
                            "No WhatsAppNumber configured for phone_number_id: %s in business %s",
                            phone_number_id,
                            business.id,
                        )
                        continue

                    access_token = decrypt_value(number.access_token_enc)

                    # Extract contact name map if provided
                    contact_names = {
                        c.wa_id: c.profile.name
                        for c in value.contacts
                        if c.profile and c.profile.name
                    }

                    # --- Process Inbound Messages ---
                    for inbound_msg in value.messages:
                        wa_message_id = inbound_msg.id
                        sender_phone = inbound_msg.from_
                        body = inbound_msg.text.body if inbound_msg.text else ""

                        # 1. Deduplication check (Meta retries)
                        existing_msg = await msg_repo.get_by_wa_message_id(wa_message_id)
                        if existing_msg:
                            logger.info("Skipping duplicate message: %s", wa_message_id)
                            continue

                        # 2. Upsert Customer
                        customer_name = contact_names.get(sender_phone)
                        customer, _ = await cust_repo.get_or_create(
                            phone=sender_phone,
                            name=customer_name,
                        )

                        # 3. Get or Create Conversation
                        conversation, _ = await conv_repo.get_or_create(
                            customer_id=customer.id,
                            number_id=number.id,
                        )

                        # 4. Store Inbound Message
                        inbound_msg_record = await msg_repo.create(
                            conversation_id=conversation.id,
                            role=MessageRole.CUSTOMER,
                            body=body,
                            wa_message_id=wa_message_id,
                            type_=inbound_msg.type,
                            status="received",
                        )

                        # Update last_customer_message_at
                        conversation.last_customer_message_at = datetime.now(UTC)
                        await session.flush()

                        # Real-time event for incoming customer message
                        await broadcaster.broadcast(
                            str(business.id),
                            "new_message",
                            {
                                "conversation_id": str(conversation.id),
                                "message_id": str(inbound_msg_record.id),
                                "role": "customer",
                                "body": body,
                            },
                        )

                        # 5. Mark as read on WhatsApp
                        if access_token:
                            await client.mark_as_read(
                                phone_number_id=phone_number_id,
                                access_token=access_token,
                                wa_message_id=wa_message_id,
                            )

                        # 6. Check if conversation is in Human mode
                        if conversation.mode == ConversationMode.HUMAN:
                            logger.info(
                                "Conversation %s is in human mode, skipping bot reply",
                                conversation.id,
                            )
                            continue

                        # 6b. Check explicit handoff intent
                        if detect_handoff_intent(body):
                            logger.info(
                                "Customer requested human handoff in conversation %s",
                                conversation.id,
                            )
                            conversation.mode = ConversationMode.HUMAN
                            conversation.needs_human = True
                            await session.flush()

                            await broadcaster.broadcast(
                                str(business.id),
                                "conversation_updated",
                                {
                                    "conversation_id": str(conversation.id),
                                    "mode": "human",
                                    "needs_human": True,
                                },
                            )

                            if access_token:
                                handoff_notice = "I have transferred your chat to our support team. A human representative will assist you shortly."
                                resp = await client.send_text(
                                    phone_number_id=phone_number_id,
                                    access_token=access_token,
                                    to=sender_phone,
                                    body=handoff_notice,
                                )
                                msg_id = (
                                    resp.get("messages", [{}])[0].get("id")
                                    if resp.get("messages")
                                    else None
                                )
                                notice_msg = await msg_repo.create(
                                    conversation_id=conversation.id,
                                    role=MessageRole.BOT,
                                    body=handoff_notice,
                                    wa_message_id=msg_id,
                                    type_="text",
                                    status="sent",
                                )
                                await broadcaster.broadcast(
                                    str(business.id),
                                    "new_message",
                                    {
                                        "conversation_id": str(conversation.id),
                                        "message_id": str(notice_msg.id),
                                        "role": "bot",
                                        "body": handoff_notice,
                                    },
                                )
                            continue

                        # 7. Check 24-hour service window
                        if not is_within_service_window(conversation.last_customer_message_at):
                            logger.warning(
                                "Outside 24-hour window for customer %s in conversation %s",
                                sender_phone,
                                conversation.id,
                            )
                            continue

                        # 8. AI Pipeline Execution (or fallback Echo if AI key not configured)
                        if business.ai_api_key_enc and access_token:
                            await process_conversation_turn(
                                session=session,
                                business=business,
                                number=number,
                                customer=customer,
                                conversation=conversation,
                                inbound_body=body,
                                access_token=access_token,
                                client=client,
                            )
                        elif access_token:
                            echo_reply = f"Echo: {body}"
                            outbound_wa_id = None
                            try:
                                resp = await client.send_text(
                                    phone_number_id=phone_number_id,
                                    access_token=access_token,
                                    to=sender_phone,
                                    body=echo_reply,
                                )
                                messages_resp = resp.get("messages", [])
                                if messages_resp:
                                    outbound_wa_id = messages_resp[0].get("id")
                            except Exception as exc:
                                logger.error("Failed to send WhatsApp echo reply: %s", exc)

                            echo_stored = await msg_repo.create(
                                conversation_id=conversation.id,
                                role=MessageRole.BOT,
                                body=echo_reply,
                                wa_message_id=outbound_wa_id,
                                type_="text",
                                status="sent" if outbound_wa_id else "failed",
                            )
                            await broadcaster.broadcast(
                                str(business.id),
                                "new_message",
                                {
                                    "conversation_id": str(conversation.id),
                                    "message_id": str(echo_stored.id),
                                    "role": "bot",
                                    "body": echo_reply,
                                },
                            )

                    # --- Process Status Callbacks ---
                    for status_item in value.statuses:
                        status_msg = await msg_repo.get_by_wa_message_id(status_item.id)
                        if status_msg:
                            status_msg.status = status_item.status
                            await session.flush()

            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("Error processing webhook in background: %s", exc, exc_info=True)
