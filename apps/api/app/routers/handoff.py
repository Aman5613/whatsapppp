"""Handoff queue and auto-return API router."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.business import BusinessRepository
from app.repositories.conversation import ConversationRepository
from app.services.handoff.service import auto_return_inactive_conversations

router = APIRouter(prefix="/api/handoff", tags=["Human Handoff"])


class HandoffItemOut(BaseModel):
    """Conversation summary item for the handoff queue."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    customer_phone: str
    mode: str
    needs_human: bool
    last_customer_message_at: datetime
    last_message_body: str | None = None
    last_message_role: str | None = None
    message_count: int = 0


class AutoReturnResponse(BaseModel):
    returned_count: int
    returned_conversation_ids: list[uuid.UUID]


@router.get("", response_model=list[HandoffItemOut])
async def list_handoff_queue(
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all conversations needing human intervention or currently handled by human."""
    biz_repo = BusinessRepository(session)
    biz = await biz_repo.get_by_id(business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    conv_repo = ConversationRepository(session, business_id=business_id)
    conversations = await conv_repo.list_handoff_queue()

    items: list[dict[str, Any]] = []
    for conv in conversations:
        # Latest message in conversation
        last_msg = conv.messages[-1] if conv.messages else None
        items.append(
            {
                "conversation_id": conv.id,
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

    return items


@router.post("/auto-return", response_model=AutoReturnResponse)
async def trigger_auto_return(
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    timeout_minutes: int = Query(default=60, ge=1, le=10080),
    session: AsyncSession = Depends(get_session),
) -> AutoReturnResponse:
    """Manually or periodically trigger auto-return for inactive human-mode conversations."""
    biz_repo = BusinessRepository(session)
    biz = await biz_repo.get_by_id(business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    returned_ids = await auto_return_inactive_conversations(
        session=session,
        business_id=business_id,
        timeout_minutes=timeout_minutes,
    )
    await session.commit()

    return AutoReturnResponse(
        returned_count=len(returned_ids),
        returned_conversation_ids=returned_ids,
    )
