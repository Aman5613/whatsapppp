"""Tests proving multi-tenant isolation across all repositories."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Business,
    Customer,
    Order,
    OrderItem,
    Product,
)
from app.repositories import (
    CustomerRepository,
    OrderRepository,
    ProductRepository,
)


@pytest.mark.anyio
async def test_product_tenant_isolation(db_session: AsyncSession):
    """Verify Business A cannot access or list products belonging to Business B."""
    biz_a = Business(name="Business A", webhook_key="key_a_123")
    biz_b = Business(name="Business B", webhook_key="key_b_456")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    prod_a = Product(
        business_id=biz_a.id,
        name="Nike Air Max",
        price=Decimal("150.00"),
        stock=5,
    )
    prod_b = Product(
        business_id=biz_b.id,
        name="Adidas Ultraboost",
        price=Decimal("180.00"),
        stock=3,
    )
    db_session.add_all([prod_a, prod_b])
    await db_session.commit()

    repo_a = ProductRepository(db_session, biz_a.id)
    repo_b = ProductRepository(db_session, biz_b.id)

    # Business A repo should only see its own product
    prods_a = await repo_a.list_all()
    assert len(prods_a) == 1
    assert prods_a[0].name == "Nike Air Max"

    # Business A cannot fetch Business B's product by ID
    assert await repo_a.get_by_id(prod_b.id) is None

    # Search in Business A should never return Business B's products
    search_results = await repo_a.search(query="Ultraboost")
    assert len(search_results) == 0

    # Business B repo should see Ultraboost
    prods_b = await repo_b.list_all()
    assert len(prods_b) == 1
    assert prods_b[0].name == "Adidas Ultraboost"


@pytest.mark.anyio
async def test_customer_tenant_isolation(db_session: AsyncSession):
    """Verify CustomerRepository scopes customers strictly to business."""
    biz_a = Business(name="Business A", webhook_key="key_a_cust")
    biz_b = Business(name="Business B", webhook_key="key_b_cust")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    cust_a = Customer(business_id=biz_a.id, phone="+1234567890", name="Alice")
    cust_b = Customer(business_id=biz_b.id, phone="+1234567890", name="Bob (Diff Business)")
    db_session.add_all([cust_a, cust_b])
    await db_session.commit()

    repo_a = CustomerRepository(db_session, biz_a.id)
    repo_b = CustomerRepository(db_session, biz_b.id)

    fetched_a = await repo_a.get_by_phone("+1234567890")
    assert fetched_a is not None
    assert fetched_a.name == "Alice"
    assert fetched_a.business_id == biz_a.id

    fetched_b = await repo_b.get_by_phone("+1234567890")
    assert fetched_b is not None
    assert fetched_b.name == "Bob (Diff Business)"
    assert fetched_b.business_id == biz_b.id


@pytest.mark.anyio
async def test_order_tenant_and_phone_isolation(db_session: AsyncSession):
    """Verify orders are isolated by business AND sender phone."""
    biz_a = Business(name="Business A", webhook_key="key_a_order")
    biz_b = Business(name="Business B", webhook_key="key_b_order")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    order_a1 = Order(
        business_id=biz_a.id,
        customer_phone="+919999999999",
        status="delivered",
        total=Decimal("50.00"),
    )
    order_a2 = Order(
        business_id=biz_a.id,
        customer_phone="+918888888888",  # different customer, same business
        status="shipped",
        total=Decimal("75.00"),
    )
    order_b1 = Order(
        business_id=biz_b.id,
        customer_phone="+919999999999",  # same phone, different business
        status="pending",
        total=Decimal("100.00"),
    )
    db_session.add_all([order_a1, order_a2, order_b1])
    await db_session.flush()

    item = OrderItem(
        order_id=order_a1.id, product_name="Socks", quantity=2, unit_price=Decimal("25.00")
    )
    db_session.add(item)
    await db_session.commit()

    repo_a = OrderRepository(db_session, biz_a.id)

    # Customer 9999999999 looking up their order in Business A
    found = await repo_a.get_by_id_and_phone(order_a1.id, "+919999999999")
    assert found is not None
    assert found.status == "delivered"
    assert len(found.items) == 1

    # Customer 9999999999 CANNOT see Customer 8888888888's order in Business A
    not_mine = await repo_a.get_by_id_and_phone(order_a2.id, "+919999999999")
    assert not_mine is None

    # Customer 9999999999 CANNOT see Business B's order using Business A's repo
    foreign_order = await repo_a.get_by_id_and_phone(order_b1.id, "+919999999999")
    assert foreign_order is None


@pytest.mark.anyio
async def test_delete_scoped_by_tenant(db_session: AsyncSession):
    """Verify deleting entity from repo A cannot delete repo B's entity."""
    biz_a = Business(name="A", webhook_key="key_del_a")
    biz_b = Business(name="B", webhook_key="key_del_b")
    db_session.add_all([biz_a, biz_b])
    await db_session.flush()

    prod_b = Product(business_id=biz_b.id, name="Secret Product", price=Decimal("10.00"))
    db_session.add(prod_b)
    await db_session.commit()

    repo_a = ProductRepository(db_session, biz_a.id)
    deleted = await repo_a.delete_by_id(prod_b.id)
    assert deleted is False

    # Product B should still exist
    repo_b = ProductRepository(db_session, biz_b.id)
    still_there = await repo_b.get_by_id(prod_b.id)
    assert still_there is not None
