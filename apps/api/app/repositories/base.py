"""Tenant-scoped base repository."""

import uuid
from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Base repository ensuring all queries are strictly filtered by business_id."""

    def __init__(self, session: AsyncSession, business_id: uuid.UUID):
        self.session = session
        self.business_id = business_id
        self.model = self._get_model_class()

    def _get_model_class(self):
        """Extract generic model type or raise NotImplementedError in subclass."""
        orig_bases = getattr(self.__class__, "__orig_bases__", [])
        for base in orig_bases:
            if hasattr(base, "__args__") and base.__args__:
                return base.__args__[0]
        raise NotImplementedError("Subclasses must declare generic model type.")

    def _scoped_query(self) -> Select:
        """Create a select query automatically scoped by business_id."""
        query = select(self.model)
        if hasattr(self.model, "business_id"):
            query = query.where(self.model.business_id == self.business_id)
        return query

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        """Get an entity by its primary key, scoped to the current business."""
        query = self._scoped_query().where(self.model.id == entity_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        """List entities scoped to the current business."""
        query = self._scoped_query().limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, entity: ModelT) -> ModelT:
        """Persist a new entity ensuring business_id is set."""
        if hasattr(entity, "business_id"):
            entity.business_id = self.business_id
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete_by_id(self, entity_id: uuid.UUID) -> bool:
        """Delete an entity by its id scoped strictly to this business."""
        stmt = delete(self.model).where(self.model.id == entity_id)
        if hasattr(self.model, "business_id"):
            stmt = stmt.where(self.model.business_id == self.business_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0
