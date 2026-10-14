"""Order repository."""

import uuid
from collections.abc import Sequence

from sqlalchemy import desc
from sqlalchemy.orm import selectinload

from app.models.order import Order
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    """Tenant-scoped order repository."""

    async def get_by_id_and_phone(
        self,
        order_id: uuid.UUID,
        customer_phone: str,
    ) -> Order | None:
        """Fetch order strictly scoped to business AND customer's phone number."""
        query = (
            self._scoped_query()
            .where(
                Order.id == order_id,
                Order.customer_phone == customer_phone,
            )
            .options(selectinload(Order.items))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_phone(
        self,
        customer_phone: str,
        limit: int = 10,
    ) -> Sequence[Order]:
        """Fetch orders for a specific customer phone within the business."""
        query = (
            self._scoped_query()
            .where(Order.customer_phone == customer_phone)
            .options(selectinload(Order.items))
            .order_by(desc(Order.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()
