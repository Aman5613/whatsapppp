"""Tests for /api/health endpoint."""

import pytest


@pytest.mark.anyio
async def test_health_returns_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.anyio
async def test_health_version_format(client):
    response = await client.get("/api/health")
    data = response.json()
    # Version should be semver-ish
    parts = data["version"].split(".")
    assert len(parts) >= 2
