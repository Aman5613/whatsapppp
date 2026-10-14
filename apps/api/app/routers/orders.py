"""Orders API router."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.order import OrderRepository
from app.services.csv_import import import_orders_csv

router = APIRouter(prefix="/api/orders", tags=["Orders"])


class OrderItemOut(BaseModel):
    product_name: str
    quantity: int
    unit_price: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_phone: str
    status: str
    total: float
    items: list[OrderItemOut]


@router.get("", response_model=list[OrderOut])
async def list_orders(
    business_id: uuid.UUID = Query(...),
    customer_phone: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List orders scoped strictly to business_id."""
    repo = OrderRepository(session, business_id)
    if customer_phone:
        orders = await repo.list_by_phone(customer_phone)
    else:
        orders = await repo.list_all(limit=100)

    return [
        OrderOut(
            id=o.id,
            customer_phone=o.customer_phone,
            status=o.status,
            total=float(o.total),
            items=[
                OrderItemOut(
                    product_name=i.product_name,
                    quantity=i.quantity,
                    unit_price=float(i.unit_price),
                )
                for i in getattr(o, "items", [])
            ],
        )
        for o in orders
    ]


@router.post("/import")
async def import_orders(
    business_id: uuid.UUID = Query(...),
    dry_run: bool = Query(False, description="Simulate import and return validation report"),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Import orders and items from CSV with dry_run validation."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content_bytes = await file.read()
    try:
        csv_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        csv_text = content_bytes.decode("latin-1")

    return await import_orders_csv(
        csv_text=csv_text,
        business_id=business_id,
        session=session,
        dry_run=dry_run,
    )
