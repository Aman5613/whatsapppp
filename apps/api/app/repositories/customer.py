"""Customer repository."""

from app.models.customer import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Tenant-scoped customer repository."""

    async def get_by_phone(self, phone: str) -> Customer | None:
        """Fetch customer by phone number within the business."""
        query = self._scoped_query().where(Customer.phone == phone)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(self, phone: str, name: str | None = None) -> tuple[Customer, bool]:
        """Get existing customer or create a new one."""
        existing = await self.get_by_phone(phone)
        if existing:
            if name and not existing.name:
                existing.name = name
                await self.session.flush()
            return existing, False

        new_customer = Customer(
            business_id=self.business_id,
            phone=phone,
            name=name,
        )
        self.session.add(new_customer)
        await self.session.flush()
        return new_customer, True
