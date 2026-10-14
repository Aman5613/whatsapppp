"""Tests for settings and database configuration endpoints."""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_value
from app.core.database import get_session
from app.main import app
from app.models import Business, WhatsAppNumber


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.anyio
async def test_settings_masked_and_update(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
):
    biz = Business(
        name="Gadget Zone",
        webhook_key="gz_webhook_123",
        ai_api_key_enc=encrypt_value("sk-proj-supersecretkey12345"),
    )
    db_session.add(biz)
    await db_session.flush()

    num = WhatsAppNumber(
        business_id=biz.id,
        phone_number_id="phone_gz_1",
        access_token_enc=encrypt_value("EAABtestaccesstoken67890"),
        app_secret_enc=encrypt_value("mocksecret123456789"),
        verify_token="gz_verify_token",
    )
    db_session.add(num)
    await db_session.commit()

    # 1. Get settings with masked keys
    resp = await client.get(f"/api/settings?business_id={biz.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["business_name"] == "Gadget Zone"
    assert data["has_ai_key"] is True
    assert "sk-" in data["ai_key_masked"]
    assert "supersecretkey" not in data["ai_key_masked"]
    assert data["whatsapp"]["has_access_token"] is True
    assert "EAA" in data["whatsapp"]["access_token_masked"]
    assert "testaccesstoken" not in data["whatsapp"]["access_token_masked"]
    assert data["webhook_url"].endswith("/gz_webhook_123")

    # 2. Patch settings
    patch_resp = await client.patch(
        f"/api/settings?business_id={biz.id}",
        json={
            "business_name": "Gadget Hub Pro",
            "system_prompt": "You are a tech specialist assistant.",
            "ai_api_key": "sk-proj-brandnewkey99999",
            "whatsapp_phone_number_id": "phone_gz_new",
        },
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()

    assert updated["business_name"] == "Gadget Hub Pro"
    assert updated["system_prompt"] == "You are a tech specialist assistant."
    assert updated["whatsapp"]["phone_number_id"] == "phone_gz_new"
    assert updated["has_ai_key"] is True


@pytest.mark.anyio
async def test_database_status_api(client: httpx.AsyncClient):
    resp = await client.get("/api/settings/database/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "connected" in data
    assert "is_sqlite" in data
