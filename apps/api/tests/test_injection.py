"""Tests proving SQL injection strings in tool inputs are harmless."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Business, Product
from app.tools.search_products import execute as execute_search


@pytest.mark.anyio
async def test_sql_injection_strings_are_harmless(db_session: AsyncSession):
    """Verify malicious SQL payloads in tool arguments do not break queries or tamper data."""
    biz = Business(name="Safe Biz", webhook_key="safe_key")
    db_session.add(biz)
    await db_session.flush()

    prod = Product(business_id=biz.id, name="Authentic Shoes", price=Decimal("100.00"), stock=5)
    db_session.add(prod)
    await db_session.commit()

    malicious_inputs = [
        "'; DROP TABLE products; --",
        "' OR '1'='1",
        "shoes' UNION SELECT * FROM users --",
        '" OR ""="',
        "1; WAITFOR DELAY '0:0:5'--",
    ]

    for evil_query in malicious_inputs:
        result = await execute_search(
            session=db_session,
            business_id=biz.id,
            customer_phone="1234567890",
            args={"query": evil_query},
        )
        # Should execute safely and simply return found=False
        assert result["found"] is False

    # Verify products table is completely intact
    prod_check = await db_session.execute(select(Product).where(Product.id == prod.id))
    assert prod_check.scalar_one_or_none() is not None
