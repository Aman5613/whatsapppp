"""Usage and Analytics API router."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.business import Business
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.usage_log import UsageLog

router = APIRouter(prefix="/api/usage", tags=["Usage & Analytics"])


class UsageLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: int
    created_at: datetime


class ModelBreakdown(BaseModel):
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float


class UsageAnalyticsOut(BaseModel):
    total_conversations: int
    total_messages: int
    total_ai_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_estimated_cost: float
    breakdown_by_model: list[ModelBreakdown]
    recent_logs: list[UsageLogOut]


def estimate_token_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Rough cost estimate per provider pricing per 1M tokens."""
    if "claude" in provider.lower():
        # ~$3/M input, $15/M output
        return round((input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000, 5)
    if "gemini" in provider.lower():
        # ~$0.075/M input, $0.30/M output
        return round((input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000, 5)
    # Default OpenAI (gpt-4o-mini ~ $0.15/M input, $0.60/M output)
    return round((input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000, 5)


@router.get("", response_model=UsageAnalyticsOut)
async def get_usage_analytics(
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve aggregated usage metrics and cost estimates."""
    biz = await session.get(Business, business_id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    # 1. Total conversations
    conv_query = select(func.count(Conversation.id)).where(Conversation.business_id == business_id)
    conv_count = (await session.execute(conv_query)).scalar() or 0

    # 2. Total messages
    msg_query = (
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.business_id == business_id)
    )
    msg_count = (await session.execute(msg_query)).scalar() or 0

    # 3. Aggregated token usage joined on conversation
    usage_sum_query = (
        select(
            func.count(UsageLog.id).label("total_calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("output_tokens"),
        )
        .join(Conversation, UsageLog.conversation_id == Conversation.id)
        .where(Conversation.business_id == business_id)
    )
    sum_row = (await session.execute(usage_sum_query)).one()

    total_in = int(sum_row.input_tokens)
    total_out = int(sum_row.output_tokens)
    total_tok = total_in + total_out
    total_cost = estimate_token_cost(biz.ai_provider, total_in, total_out)

    # 4. Breakdown by model
    breakdown_query = (
        select(
            UsageLog.provider,
            UsageLog.model,
            func.count(UsageLog.id).label("calls"),
            func.coalesce(func.sum(UsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(UsageLog.output_tokens), 0).label("output_tokens"),
        )
        .join(Conversation, UsageLog.conversation_id == Conversation.id)
        .where(Conversation.business_id == business_id)
        .group_by(UsageLog.provider, UsageLog.model)
    )
    breakdown_rows = (await session.execute(breakdown_query)).all()
    breakdown = [
        {
            "provider": r.provider,
            "model": r.model,
            "calls": r.calls,
            "input_tokens": int(r.input_tokens),
            "output_tokens": int(r.output_tokens),
            "total_tokens": int(r.input_tokens) + int(r.output_tokens),
            "estimated_cost": estimate_token_cost(
                r.provider, int(r.input_tokens), int(r.output_tokens)
            ),
        }
        for r in breakdown_rows
    ]

    # 5. Recent 20 logs
    recent_query = (
        select(UsageLog)
        .join(Conversation, UsageLog.conversation_id == Conversation.id)
        .where(Conversation.business_id == business_id)
        .order_by(desc(UsageLog.created_at))
        .limit(20)
    )
    recent_logs = (await session.execute(recent_query)).scalars().all()

    formatted_logs = [
        {
            "id": log_item.id,
            "conversation_id": log_item.conversation_id,
            "provider": log_item.provider,
            "model": log_item.model,
            "input_tokens": log_item.input_tokens,
            "output_tokens": log_item.output_tokens,
            "total_tokens": log_item.input_tokens + log_item.output_tokens,
            "latency_ms": log_item.latency_ms,
            "created_at": log_item.created_at,
        }
        for log_item in recent_logs
    ]

    return {
        "total_conversations": conv_count,
        "total_messages": msg_count,
        "total_ai_calls": sum_row.total_calls,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_tokens": total_tok,
        "total_estimated_cost": total_cost,
        "breakdown_by_model": breakdown,
        "recent_logs": formatted_logs,
    }
