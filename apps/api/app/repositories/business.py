"""Business repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business


class BusinessRepository:
    """Repository for business entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, business_id: uuid.UUID) -> Business | None:
        """Fetch business by ID."""
        query = select(Business).where(Business.id == business_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_webhook_key(self, webhook_key: str) -> Business | None:
        """Find business by unique webhook key."""
        query = select(Business).where(Business.webhook_key == webhook_key)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, business: Business) -> Business:
        """Create a business."""
        self.session.add(business)
        await self.session.flush()
        return business
