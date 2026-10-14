"""Tests for management CLI."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import _create_business, ph
from app.models import Business, User


@pytest.mark.anyio
async def test_create_business_cli_logic(db_session: AsyncSession, monkeypatch):
    """Test business and user creation with Argon2 password hashing."""

    # Monkeypatch async_session_factory to yield our test db_session
    class MockSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    import app.cli

    monkeypatch.setattr(app.cli, "async_session_factory", MockSessionFactory())

    await _create_business(
        name="Test Auto Store",
        email="owner@autostore.com",
        password="MySecretPassword123!",
    )

    # Verify Business
    biz_stmt = select(Business).where(Business.name == "Test Auto Store")
    biz_res = await db_session.execute(biz_stmt)
    biz = biz_res.scalar_one_or_none()
    assert biz is not None
    assert biz.webhook_key is not None

    # Verify User & Argon2 password verification
    user_stmt = select(User).where(User.email == "owner@autostore.com")
    user_res = await db_session.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    assert user is not None
    assert user.business_id == biz.id

    # Password must verify correctly and plaintext is NOT stored
    assert user.password_hash != "MySecretPassword123!"
    assert ph.verify(user.password_hash, "MySecretPassword123!") is True


@pytest.mark.anyio
async def test_cleanup_retention_cli_logic(db_session: AsyncSession, monkeypatch):
    """Test cleanup-retention command purges historical messages and logs."""
    from datetime import UTC, datetime, timedelta

    from app.cli import _cleanup_retention
    from app.models import Conversation, Customer, Message, MessageRole, UsageLog, WhatsAppNumber

    class MockSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    import app.cli

    monkeypatch.setattr(app.cli, "async_session_factory", MockSessionFactory())

    biz = Business(name="Retention Store", webhook_key="ret_key")
    db_session.add(biz)
    await db_session.flush()

    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_ret",
        access_token_enc="",
        app_secret_enc="",
        verify_token="tok",
    )
    cust = Customer(business_id=biz.id, phone="+919876543210")
    db_session.add_all([num, cust])
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=num.id,
    )
    db_session.add(conv)
    await db_session.flush()

    old_time = datetime.now(UTC) - timedelta(days=120)
    msg_old = Message(
        conversation_id=conv.id,
        role=MessageRole.CUSTOMER,
        body="Old message to purge",
        created_at=old_time,
    )
    msg_new = Message(
        conversation_id=conv.id,
        role=MessageRole.CUSTOMER,
        body="Recent message to keep",
    )
    log_old = UsageLog(
        conversation_id=conv.id,
        provider="openai",
        model="gpt-4o-mini",
        created_at=old_time,
    )
    db_session.add_all([msg_old, msg_new, log_old])
    await db_session.commit()

    # 1. Dry run
    await _cleanup_retention(days=90, dry_run=True)
    msgs_after_dry = (await db_session.execute(select(Message))).scalars().all()
    assert len(msgs_after_dry) == 2

    # 2. Live purge
    await _cleanup_retention(days=90, dry_run=False)
    msgs_after_purge = (await db_session.execute(select(Message))).scalars().all()
    assert len(msgs_after_purge) == 1
    assert msgs_after_purge[0].body == "Recent message to keep"

    logs_after_purge = (await db_session.execute(select(UsageLog))).scalars().all()
    assert len(logs_after_purge) == 0


@pytest.mark.anyio
async def test_delete_customer_data_cli_logic(db_session: AsyncSession, monkeypatch):
    """Test delete-data command removes customer and cascades to conversations and messages."""
    from app.cli import _delete_customer_data
    from app.models import Conversation, Customer, Message, MessageRole, WhatsAppNumber

    class MockSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    import app.cli

    monkeypatch.setattr(app.cli, "async_session_factory", MockSessionFactory())

    biz = Business(name="Delete Data Store", webhook_key="del_key")
    db_session.add(biz)
    await db_session.flush()

    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="num_del",
        access_token_enc="",
        app_secret_enc="",
        verify_token="tok",
    )
    cust = Customer(business_id=biz.id, phone="+919999888877")
    db_session.add_all([num, cust])
    await db_session.flush()

    conv = Conversation(
        business_id=biz.id,
        customer_id=cust.id,
        number_id=num.id,
    )
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.CUSTOMER,
        body="Sensitive message to delete",
    )
    db_session.add(msg)
    await db_session.commit()

    # Dry run
    await _delete_customer_data(str(biz.id), "+919999888877", dry_run=True)
    cust_res = (await db_session.execute(select(Customer).where(Customer.id == cust.id))).scalar_one_or_none()
    assert cust_res is not None

    # Live delete
    await _delete_customer_data(str(biz.id), "+919999888877", dry_run=False)
    cust_res = (await db_session.execute(select(Customer).where(Customer.id == cust.id))).scalar_one_or_none()
    assert cust_res is None

    # Messages cascaded
    msg_res = (await db_session.execute(select(Message).where(Message.id == msg.id))).scalar_one_or_none()
    assert msg_res is None


