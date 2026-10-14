"""Product repository."""

from collections.abc import Sequence
from decimal import Decimal

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Tenant-scoped product repository."""

    async def search(
        self,
        query: str | None = None,
        category: str | None = None,
        max_price: Decimal | None = None,
        limit: int = 10,
    ) -> Sequence[Product]:
        """Search products with full-text / ILIKE filter, scoped to business and active stock."""
        stmt = self._scoped_query().where(Product.active.is_(True))

        if category:
            stmt = stmt.where(Product.category.ilike(f"%{category}%"))

        if max_price is not None:
            stmt = stmt.where(Product.price <= max_price)

        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(Product.name.ilike(pattern) | Product.description.ilike(pattern))

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
