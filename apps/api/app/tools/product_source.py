"""Database implementation of ProductSource."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.product import ProductRepository
from app.tools.interfaces import ProductSource


class DatabaseProductSource(ProductSource):
    """Product source querying the local PostgreSQL products table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        business_id: uuid.UUID,
        query: str | None = None,
        category: str | None = None,
        max_price: Decimal | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search products using parameterized repository queries strictly scoped to business_id."""
        repo = ProductRepository(self.session, business_id)
        products = await repo.search(
            query=query,
            category=category,
            max_price=max_price,
            limit=limit,
        )

        return [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "price": float(p.price),
                "stock": p.stock,
                "in_stock": p.stock > 0,
            }
            for p in products
        ]
