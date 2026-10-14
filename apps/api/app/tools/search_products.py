"""search_products tool definition and executor."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.types import ToolSpec
from app.tools.interfaces import ProductSource
from app.tools.product_source import DatabaseProductSource

SPEC = ToolSpec(
    name="search_products",
    description="Search the store's product catalog for available items, prices, and stock.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Product search term (e.g. 'sneakers', 'saree', 't-shirt')",
            },
            "category": {
                "type": "string",
                "description": "Optional category filter (e.g. 'footwear', 'clothing')",
            },
            "max_price": {
                "type": "number",
                "description": "Optional maximum price filter in local currency",
            },
        },
        "required": [],
    },
)


async def execute(
    session: AsyncSession,
    business_id: uuid.UUID,
    customer_phone: str,
    args: dict[str, Any],
    product_source: ProductSource | None = None,
) -> dict[str, Any]:
    """Execute search_products query scoped strictly to business_id."""
    source = product_source or DatabaseProductSource(session)

    query = args.get("query")
    category = args.get("category")
    max_price_num = args.get("max_price")
    max_price = Decimal(str(max_price_num)) if max_price_num is not None else None

    products = await source.search(
        business_id=business_id,
        query=query,
        category=category,
        max_price=max_price,
        limit=5,
    )

    if not products:
        return {
            "found": False,
            "message": "No matching products found in stock.",
            "products": [],
        }

    return {
        "found": True,
        "count": len(products),
        "products": products,
    }
