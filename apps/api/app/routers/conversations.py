"""Conversations and Operator Chat API router."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.events import broadcaster
from app.models.conversation import ConversationMode
from app.repositories.business import BusinessRepository
from app.repositories.conversation import ConversationRepository
from app.services.handoff.service import (
    ConversationNotFoundError,
    ServiceWindowExpiredError,
    WhatsAppDeliveryError,
    send_human_reply,
    transition_to_bot,
    transition_to_human,
)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    type: str
    body: str
    wa_message_id: str | None = None
    status: str
    created_at: datetime


class ConversationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    customer_phone: str
    mode: str
    needs_human: bool
    last_customer_message_at: datetime
    last_message_body: str | None = None
    last_message_role: str | None = None
    message_count: int = 0


class ConversationDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    customer_phone: str
    number_id: uuid.UUID
    phone_number_id: str | None = None
    mode: str
    needs_human: bool
    last_customer_message_at: datetime
    created_at: datetime
    messages: list[MessageOut]


class SendMessageRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4096)


class TransitionResponse(BaseModel):
    id: uuid.UUID
    mode: str
    needs_human: bool
    message: str


@router.get("", response_model=list[ConversationSummaryOut])
async def list_conversations(
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    mode: str | None = Query(None, description="Filter by mode: 'bot' or 'human'"),
    needs_human: bool | None = Query(None, description="Filter by needs_human flag"),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List recent conversations for a business with optional filtering."""
    biz_repo = BusinessRepository(session)
    biz = await biz_repo.get_by_id(business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    conv_mode = None
    if mode:
        try:
            conv_mode = ConversationMode(mode.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: '{mode}'. Valid modes are 'bot' or 'human'.",
            ) from None

    conv_repo = ConversationRepository(session, business_id=business_id)
    conversations = await conv_repo.list_recent(
        limit=limit,
        mode=conv_mode,
        needs_human=needs_human,
    )

    summaries: list[dict[str, Any]] = []
    for conv in conversations:
        last_msg = conv.messages[-1] if conv.messages else None
        summaries.append(
            {
                "id": conv.id,
                "customer_id": conv.customer.id if conv.customer else conv.customer_id,
                "customer_name": conv.customer.name if conv.customer else None,
                "customer_phone": conv.customer.phone if conv.customer else "",
                "mode": conv.mode.value if hasattr(conv.mode, "value") else str(conv.mode),
                "needs_human": conv.needs_human,
                "last_customer_message_at": conv.last_customer_message_at,
                "last_message_body": last_msg.body if last_msg else None,
                "last_message_role": (
                    last_msg.role.value
                    if last_msg and hasattr(last_msg.role, "value")
                    else (str(last_msg.role) if last_msg else None)
                ),
                "message_count": len(conv.messages),
            }
        )

    return summaries


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get conversation details with all historical messages."""
    conv_repo = ConversationRepository(session, business_id=business_id)
    conv = await conv_repo.get_with_messages(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_data = [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
            "type": m.type,
            "body": m.body,
            "wa_message_id": m.wa_message_id,
            "status": m.status,
            "created_at": m.created_at,
        }
        for m in conv.messages
    ]

    return {
        "id": conv.id,
        "business_id": conv.business_id,
        "customer_id": conv.customer.id if conv.customer else conv.customer_id,
        "customer_name": conv.customer.name if conv.customer else None,
        "customer_phone": conv.customer.phone if conv.customer else "",
        "number_id": conv.number.id if conv.number else conv.number_id,
        "phone_number_id": conv.number.phone_number_id if conv.number else None,
        "mode": conv.mode.value if hasattr(conv.mode, "value") else str(conv.mode),
        "needs_human": conv.needs_human,
        "last_customer_message_at": conv.last_customer_message_at,
        "created_at": conv.created_at,
        "messages": messages_data,
    }


@router.post("/{conversation_id}/take-over", response_model=TransitionResponse)
async def take_over_conversation(
    conversation_id: uuid.UUID,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> TransitionResponse:
    """Human operator takes over conversation (mode -> human, needs_human -> False)."""
    conv_repo = ConversationRepository(session, business_id=business_id)
    conv = await conv_repo.get_with_messages(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await transition_to_human(session, conv, needs_human=False)
    await session.commit()

    await broadcaster.broadcast(
        str(business_id),
        "conversation_updated",
        {"conversation_id": str(conv.id), "mode": "human", "needs_human": False},
    )

    return TransitionResponse(
        id=conv.id,
        mode=conv.mode.value if hasattr(conv.mode, "value") else str(conv.mode),
        needs_human=conv.needs_human,
        message="Conversation successfully transferred to human operator.",
    )


@router.post("/{conversation_id}/return-to-bot", response_model=TransitionResponse)
async def return_conversation_to_bot(
    conversation_id: uuid.UUID,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> TransitionResponse:
    """Return conversation to AI bot (mode -> bot, needs_human -> False)."""
    conv_repo = ConversationRepository(session, business_id=business_id)
    conv = await conv_repo.get_with_messages(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await transition_to_bot(session, conv)
    await session.commit()

    await broadcaster.broadcast(
        str(business_id),
        "conversation_updated",
        {"conversation_id": str(conv.id), "mode": "bot", "needs_human": False},
    )

    return TransitionResponse(
        id=conv.id,
        mode=conv.mode.value if hasattr(conv.mode, "value") else str(conv.mode),
        needs_human=conv.needs_human,
        message="Conversation returned to AI bot.",
    )


@router.post("/{conversation_id}/messages", response_model=MessageOut)
async def post_operator_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Send an outbound human message to the customer via WhatsApp."""
    try:
        msg = await send_human_reply(
            session=session,
            conversation_id=conversation_id,
            business_id=business_id,
            body=payload.body,
        )
        await session.commit()
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except ServiceWindowExpiredError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except WhatsAppDeliveryError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    # Broadcast new outbound message in real-time
    await broadcaster.broadcast(
        str(business_id),
        "new_message",
        {
            "conversation_id": str(conversation_id),
            "message_id": str(msg.id),
            "role": "human",
            "body": msg.body,
        },
    )

    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
        "type": msg.type,
        "body": msg.body,
        "wa_message_id": msg.wa_message_id,
        "status": msg.status,
        "created_at": msg.created_at,
    }
