"""Tests for search_products tool."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Product
from app.tools.search_products import execute


@pytest.mark.anyio
async def test_search_products_filters_and_isolation(db_session: AsyncSession):
    """Verify search_products tool respects filters and strictly isolates by business."""
    biz_a = Business(name="Biz A", webhook_key="key_sp_a")
    biz_b = Business(name="Biz B", webhook_key="key_sp_b")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    p1 = Product(
        business_id=biz_a.id,
        name="Red Running Shoes",
        category="Shoes",
        price=Decimal("1500.00"),
        stock=10,
    )
    p2 = Product(
        business_id=biz_a.id,
        name="Blue Suede Shoes",
        category="Shoes",
        price=Decimal("3500.00"),
        stock=2,
    )
    p3 = Product(
        business_id=biz_a.id,
        name="Cotton T-Shirt",
        category="Apparel",
        price=Decimal("799.00"),
        stock=50,
    )
    # Business B product (same name as p1)
    p4 = Product(
        business_id=biz_b.id,
        name="Red Running Shoes (Biz B)",
        category="Shoes",
        price=Decimal("999.00"),
        stock=8,
    )

    db_session.add_all([p1, p2, p3, p4])
    await db_session.commit()

    # 1. Search with query and max_price under Biz A
    res = await execute(
        session=db_session,
        business_id=biz_a.id,
        customer_phone="919999900000",
        args={"query": "Shoes", "max_price": 2000},
    )

    assert res["found"] is True
    assert res["count"] == 1
    assert res["products"][0]["name"] == "Red Running Shoes"
    assert res["products"][0]["price"] == 1500.0

    # 2. Search under Biz A should NEVER return Biz B's product
    res_b_search = await execute(
        session=db_session,
        business_id=biz_a.id,
        customer_phone="919999900000",
        args={"query": "Biz B"},
    )
    assert res_b_search["found"] is False
    assert len(res_b_search["products"]) == 0
