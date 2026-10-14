"""Test security headers and request tracing middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_security_headers_present():
    """Verify security headers are applied to HTTP responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    headers = response.headers

    assert "X-Request-ID" in headers
    assert len(headers["X-Request-ID"]) > 0
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-XSS-Protection"] == "1; mode=block"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in headers["Permissions-Policy"]


@pytest.mark.asyncio
async def test_custom_request_id_preserved():
    """If client passes X-Request-ID, the same ID is returned."""
    custom_id = "req-custom-trace-999"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/health",
            headers={"X-Request-ID": custom_id},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id
