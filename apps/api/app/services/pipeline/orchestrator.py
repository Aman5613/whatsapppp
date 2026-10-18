"""Conversation reply pipeline orchestrator with per-conversation locking."""

import asyncio
import json
import logging
import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.conversation import Conversation, ConversationMode
from app.models.customer import Customer
from app.models.message import MessageRole
from app.models.usage_log import UsageLog
from app.models.whatsapp_number import WhatsAppNumber
from app.repositories import MessageRepository
from app.services.ai.registry import get_providers_for_business
from app.services.ai.retry import generate_with_fallback
from app.services.ai.types import Msg
from app.services.memory.loader import load_conversation_history
from app.services.pipeline.rate_limit import customer_rate_limiter
from app.services.pipeline.system_prompt import build_system_prompt
from app.core.events import broadcaster
from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.window import is_within_service_window
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

# In-process per-conversation locks ensuring sequential execution of rapid incoming messages
_conversation_locks: dict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

_RATE_LIMIT_MESSAGE = (
    "You are sending messages too quickly. Please wait a moment before sending another message."
)
_FALLBACK_ERROR_MESSAGE = "We are currently experiencing a brief technical issue. Our team has been notified and will assist you shortly."


async def process_conversation_turn(
    session: AsyncSession,
    business: Business,
    number: WhatsAppNumber,
    customer: Customer,
    conversation: Conversation,
    inbound_body: str,
    access_token: str,
    client: WhatsAppClient | None = None,
) -> None:
    """Execute the full AI reply pipeline under a per-conversation lock."""
    client = client or WhatsAppClient()
    lock = _conversation_locks[conversation.id]

    async with lock:
        msg_repo = MessageRepository(session)

        # 1. Check if conversation has been handed over to human
        if conversation.mode == ConversationMode.HUMAN:
            logger.info("Conversation %s is in human mode. Bot reply suppressed.", conversation.id)
            return

        # 2. Rate limit check
        if not customer_rate_limiter.is_allowed(customer.phone):
            logger.warning("Customer %s rate limited.", customer.phone)
            await client.send_text(
                phone_number_id=number.phone_number_id,
                access_token=access_token,
                to=customer.phone,
                body=_RATE_LIMIT_MESSAGE,
            )
            return

        # 3. Check 24-hour customer service window
        if not is_within_service_window(conversation.last_customer_message_at):
            logger.warning("Outside 24-hour service window for customer %s.", customer.phone)
            return

        # 4. Load memory history (trimmed to token budget)
        history_limit = getattr(business, "history_limit", 20)
        messages = await load_conversation_history(
            session=session,
            conversation_id=conversation.id,
            limit=history_limit,
            max_tokens=4000,
        )

        # 5. Build system prompt
        system_prompt = build_system_prompt(business)

        # 6. Retrieve configured AI providers and tool specifications
        primary_provider, fallback_provider = get_providers_for_business(business)
        if not primary_provider:
            logger.error("No AI provider configured for business: %s", business.id)
            return

        available_tools = tool_registry.get_specs()

        # 7. Multi-turn Tool Calling Loop (capped at 5 iterations)
        reply_text = None
        total_input_tokens = 0
        total_output_tokens = 0
        total_latency_ms = 0
        used_provider = primary_provider.provider_name
        used_model = primary_provider.model

        try:
            for _loop_iteration in range(5):
                llm_result = await generate_with_fallback(
                    primary=primary_provider,
                    fallback=fallback_provider,
                    system=system_prompt,
                    messages=messages,
                    tools=available_tools,
                )

                total_input_tokens += llm_result.usage.input_tokens
                total_output_tokens += llm_result.usage.output_tokens
                total_latency_ms += llm_result.latency_ms
                used_provider = llm_result.provider
                used_model = llm_result.model

                # If no tool calls were generated, we have our final text reply
                if not llm_result.tool_calls:
                    reply_text = llm_result.text
                    break

                # Append assistant message with requested tool calls to history
                messages.append(
                    Msg(
                        role="assistant",
                        content=llm_result.text,
                        tool_calls=llm_result.tool_calls,
                    )
                )

                # Execute each tool call and append tool_result messages
                for tc in llm_result.tool_calls:
                    tool_output, _ = await tool_registry.execute(
                        name=tc.name,
                        args=tc.arguments,
                        session=session,
                        business_id=business.id,
                        customer_phone=customer.phone,
                        conversation=conversation,
                    )
                    messages.append(
                        Msg(
                            role="tool_result",
                            tool_call_id=tc.id,
                            content=json.dumps(tool_output),
                        )
                    )

            if not reply_text:
                reply_text = llm_result.text or _FALLBACK_ERROR_MESSAGE

            usage_record = UsageLog(
                conversation_id=conversation.id,
                provider=used_provider,
                model=used_model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                latency_ms=total_latency_ms,
            )
        except Exception as exc:
            logger.error(
                "LLM generation loop failed for conversation %s: %s",
                conversation.id,
                exc,
                exc_info=True,
            )
            reply_text = _FALLBACK_ERROR_MESSAGE
            usage_record = None

        # 8. Send WhatsApp reply
        outbound_wa_id = None
        try:
            resp = await client.send_text(
                phone_number_id=number.phone_number_id,
                access_token=access_token,
                to=customer.phone,
                body=reply_text,
            )
            sent_msgs = resp.get("messages", [])
            if sent_msgs:
                outbound_wa_id = sent_msgs[0].get("id")
        except Exception as exc:
            logger.error("Failed to send WhatsApp message via Graph API: %s", exc)

        # 9. Store outbound message
        bot_msg = await msg_repo.create(
            conversation_id=conversation.id,
            role=MessageRole.BOT,
            body=reply_text,
            wa_message_id=outbound_wa_id,
            status="sent" if outbound_wa_id else "failed",
        )

        # 10. Persist usage log if available
        if usage_record:
            session.add(usage_record)

        await session.commit()

        await broadcaster.broadcast(
            str(business.id),
            "new_message",
            {
                "conversation_id": str(conversation.id),
                "message_id": str(bot_msg.id),
                "role": "bot",
                "body": reply_text,
            },
        )
