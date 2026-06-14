"""Integration tests for MCP server CRUD API."""

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_mcp_server(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/mcp", json={
        "name": "weather-api",
        "transport": "sse",
        "url": "http://localhost:8080/sse",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "weather-api"
    assert data["transport"] == "sse"
    assert data["url"] == "http://localhost:8080/sse"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_mcp_servers(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    await async_client.post("/api/mcp", json={
        "name": "server-1",
        "transport": "sse",
        "url": "http://localhost:8081/sse",
    }, headers=headers)

    resp = await async_client.get("/api/mcp", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(s["name"] == "server-1" for s in data)


@pytest.mark.asyncio
async def test_update_mcp_server(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/mcp", json={
        "name": "old-name",
        "transport": "sse",
        "url": "http://localhost:8080/sse",
    }, headers=headers)
    server_id = resp.json()["id"]

    resp = await async_client.put(f"/api/mcp/{server_id}", json={
        "name": "new-name",
        "enabled": False,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "new-name"
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_mcp_server(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/mcp", json={
        "name": "to-delete",
        "transport": "sse",
        "url": "http://localhost:8080/sse",
    }, headers=headers)
    server_id = resp.json()["id"]

    resp = await async_client.delete(f"/api/mcp/{server_id}", headers=headers)
    assert resp.status_code == 200

    resp = await async_client.get("/api/mcp", headers=headers)
    assert all(s["id"] != server_id for s in resp.json())