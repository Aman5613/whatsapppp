"""Abstract interface for product inventory data sources."""

import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class ProductSource(ABC):
    """Abstract interface for product lookups.

    Allows replacing the local database product catalog with Shopify, WooCommerce,
    or external ERPs in the future without altering LLM tool definitions.
    """

    @abstractmethod
    async def search(
        self,
        business_id: uuid.UUID,
        query: str | None = None,
        category: str | None = None,
        max_price: Decimal | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search products and return list of product dictionaries."""
        ...
