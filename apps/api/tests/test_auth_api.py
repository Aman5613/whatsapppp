"""Tests for authentication API endpoints."""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.main import app


@pytest.fixture(autouse=True)
def override_db(db_session: AsyncSession):
    async def _get_test_session():
        yield db_session

    app.dependency_overrides[get_session] = _get_test_session
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.mark.anyio
async def test_auth_status_and_setup_flow(client: httpx.AsyncClient):
    # 1. Initial status -> not initialized
    status_resp = await client.get("/api/auth/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["initialized"] is False

    # 2. Setup initial business & admin
    setup_resp = await client.post(
        "/api/auth/setup",
        json={
            "business_name": "Acme Electronics",
            "email": "admin@acme.com",
            "password": "StrongPassword123!",
        },
    )
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()
    assert setup_data["email"] == "admin@acme.com"
    assert setup_data["business_name"] == "Acme Electronics"
    assert "access_token" in setup_resp.cookies

    # 3. Subsequent status -> initialized
    status_resp2 = await client.get("/api/auth/status")
    assert status_resp2.status_code == 200
    assert status_resp2.json()["initialized"] is True

    # 4. Subsequent setup -> rejected 400
    setup_dup = await client.post(
        "/api/auth/setup",
        json={
            "business_name": "Another Store",
            "email": "hacker@test.com",
            "password": "Password123!",
        },
    )
    assert setup_dup.status_code == 400

    # 5. /api/auth/me using cookie
    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@acme.com"

    # 6. Logout
    logout_resp = await client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # 7. Login with valid credentials
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "email": "admin@acme.com",
            "password": "StrongPassword123!",
        },
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["business_name"] == "Acme Electronics"

    # 8. Login with invalid password -> 401
    bad_login = await client.post(
        "/api/auth/login",
        json={
            "email": "admin@acme.com",
            "password": "WrongPassword999",
        },
    )
    assert bad_login.status_code == 401
