"""get_order_status tool definition and executor."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.order import OrderRepository
from app.services.ai.types import ToolSpec

SPEC = ToolSpec(
    name="get_order_status",
    description="Retrieve status, items, and total for a specific customer order. Scoped strictly to the customer's phone number.",
    parameters={
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The order ID or reference number given to the customer",
            },
        },
        "required": ["order_id"],
    },
)


async def execute(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_phone: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Execute order lookup strictly isolated by business_id AND customer_phone."""
    raw_order_id = str(args.get("order_id", "")).strip()
    if not raw_order_id:
        return {"found": False, "message": "Please provide a valid order ID."}

    repo = OrderRepository(session, business_id)

    # Attempt lookup by UUID
    try:
        parsed_uuid = uuid.UUID(raw_order_id)
        order = await repo.get_by_id_and_phone(parsed_uuid, customer_phone)
    except ValueError:
        # If not a standard UUID, search customer's orders and match id prefix/suffix
        customer_orders = await repo.list_by_phone(customer_phone, limit=20)
        order = next(
            (
                o
                for o in customer_orders
                if str(o.id).startswith(raw_order_id) or str(o.id).endswith(raw_order_id)
            ),
            None,
        )

    if not order:
        return {
            "found": False,
            "message": "Order not found under your registered phone number. Please check the order number.",
        }

    items_summary = [
        {
            "product": item.product_name,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
        }
        for item in order.items
    ]

    return {
        "found": True,
        "order_id": str(order.id),
        "status": order.status,
        "total": float(order.total),
        "items": items_summary,
        "ordered_at": order.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if order.created_at
        else None,
    }
