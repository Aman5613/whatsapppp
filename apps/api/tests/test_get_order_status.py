"""Tests for get_order_status tool."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Order, OrderItem
from app.tools.get_order_status import execute


@pytest.mark.anyio
async def test_get_order_status_success_and_cross_customer_isolation(db_session: AsyncSession):
    """Verify order lookup succeeds for owner but fails for other customers."""
    biz = Business(name="Order Biz", webhook_key="key_ord_test")
    db_session.add(biz)
    await db_session.flush()

    # Customer 1 Order
    order_1 = Order(
        business_id=biz.id,
        customer_phone="919876543210",
        status="shipped",
        total=Decimal("2500.00"),
    )
    db_session.add(order_1)
    await db_session.flush()

    item = OrderItem(
        order_id=order_1.id, product_name="Silk Kurta", quantity=1, unit_price=Decimal("2500.00")
    )
    db_session.add(item)
    await db_session.commit()

    # 1. Customer 1 looking up their own order -> SUCCESS
    res_owner = await execute(
        session=db_session,
        business_id=biz.id,
        customer_phone="919876543210",
        args={"order_id": str(order_1.id)},
    )
    assert res_owner["found"] is True
    assert res_owner["status"] == "shipped"
    assert res_owner["total"] == 2500.0
    assert len(res_owner["items"]) == 1
    assert res_owner["items"][0]["product"] == "Silk Kurta"

    # 2. Customer 2 trying to look up Customer 1's order -> NOT FOUND (Privacy preserved!)
    res_stranger = await execute(
        session=db_session,
        business_id=biz.id,
        customer_phone="919999999999",  # different customer phone
        args={"order_id": str(order_1.id)},
    )
    assert res_stranger["found"] is False
    assert "not found" in res_stranger["message"].lower()
