"""Server-Sent Events (SSE) router for real-time dashboard updates."""

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.core.events import broadcaster

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", summary="Stream real-time tenant events (SSE)")
async def stream_events(
    request: Request,
    business_id: uuid.UUID = Query(..., description="Business ID (tenant)"),
) -> StreamingResponse:
    """Server-Sent Events endpoint streaming real-time notifications for conversations and handoff."""
    biz_key = str(business_id)
    queue = broadcaster.subscribe(biz_key)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Initial handshake
            yield f"event: connected\ndata: {json.dumps({'business_id': biz_key})}\n\n"
            while True:
                if await request.is_disconnected():
                    break

                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_type = payload.get("type", "message")
                    data_str = json.dumps(payload.get("data", {}))
                    yield f"event: {event_type}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep HTTP connection alive through reverse proxies
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(biz_key, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
