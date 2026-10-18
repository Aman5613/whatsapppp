"""In-memory event broadcaster for Server-Sent Events (SSE) real-time streaming."""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class EventBroadcaster:
    """Manages real-time event subscribers per tenant (business_id)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, business_id: str) -> asyncio.Queue:
        """Register a new event queue for a tenant."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        biz_key = str(business_id)
        if biz_key not in self._subscribers:
            self._subscribers[biz_key] = set()
        self._subscribers[biz_key].add(queue)
        return queue

    def unsubscribe(self, business_id: str, queue: asyncio.Queue) -> None:
        """Remove an event queue for a tenant."""
        biz_key = str(business_id)
        if biz_key in self._subscribers:
            self._subscribers[biz_key].discard(queue)
            if not self._subscribers[biz_key]:
                del self._subscribers[biz_key]

    async def broadcast(self, business_id: str, event_type: str, data: dict[str, Any]) -> None:
        """Dispatch an event to all active subscribers for the business."""
        biz_key = str(business_id)
        subscribers = self._subscribers.get(biz_key)
        if not subscribers:
            return

        payload = {"type": event_type, "data": data}
        for queue in list(subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Event queue full, dropping event", business_id=biz_key)
            except Exception as exc:
                logger.warning("Failed to queue event", error=str(exc))


broadcaster = EventBroadcaster()
