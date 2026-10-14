"""Tests for product and order CSV import service."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Order, Product
from app.services.csv_import import import_orders_csv, import_products_csv


@pytest.mark.anyio
async def test_products_csv_import_dry_run_and_persist(db_session: AsyncSession):
    """Verify dry run generates error report without saving, and live run persists valid items."""
    biz = Business(name="CSV Biz", webhook_key="csv_key")
    db_session.add(biz)
    await db_session.commit()

    csv_content = """name,price,stock,category,description
Classic Sneaker,1499.00,10,Footwear,Comfortable casual sneaker
Invalid Item,-50.00,5,Misc,Negative price error
Bad Stock Item,800.00,not_a_number,Apparel,Stock error
Running Shorts,599.00,25,Apparel,Lightweight shorts
"""

    # 1. Dry run
    dry_report = await import_products_csv(
        csv_text=csv_content,
        business_id=biz.id,
        session=db_session,
        dry_run=True,
    )

    assert dry_report["total_rows"] == 4
    assert dry_report["valid_rows"] == 2
    assert dry_report["error_count"] == 2
    assert dry_report["dry_run"] is True
    assert len(dry_report["errors"]) == 2

    # Verify no products were written during dry_run
    p_check = await db_session.execute(select(Product).where(Product.business_id == biz.id))
    assert len(p_check.scalars().all()) == 0

    # 2. Live import
    live_report = await import_products_csv(
        csv_text=csv_content,
        business_id=biz.id,
        session=db_session,
        dry_run=False,
    )
    assert live_report["valid_rows"] == 2

    # Verify 2 valid products were saved
    p_live = await db_session.execute(select(Product).where(Product.business_id == biz.id))
    saved_prods = p_live.scalars().all()
    assert len(saved_prods) == 2
    names = [p.name for p in saved_prods]
    assert "Classic Sneaker" in names
    assert "Running Shorts" in names


@pytest.mark.anyio
async def test_orders_csv_import(db_session: AsyncSession):
    """Verify orders and nested order items import properly."""
    biz = Business(name="CSV Order Biz", webhook_key="csv_ord_key")
    db_session.add(biz)
    await db_session.commit()

    csv_content = """customer_phone,product_name,quantity,unit_price,status
+919876543210,Nike Air Max,1,8500.00,shipped
+919876543210,Ankle Socks,3,200.00,shipped
"""

    report = await import_orders_csv(
        csv_text=csv_content,
        business_id=biz.id,
        session=db_session,
        dry_run=False,
    )

    assert report["valid_rows"] == 2
    assert report["error_count"] == 0

    orders_res = await db_session.execute(select(Order).where(Order.business_id == biz.id))
    orders = orders_res.scalars().all()
    assert len(orders) == 2
