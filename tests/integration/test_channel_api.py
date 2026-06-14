"""Integration tests for channel CRUD API."""

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_channel(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {"app_key": "test-key", "app_secret": "test-secret"},
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["channel_type"] == "dingtalk"
    assert data["config"]["app_key"] == "test-key"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_channels(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    # Create a channel first
    await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)

    resp = await async_client.get("/api/channels", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(c["channel_type"] == "dingtalk" for c in data)


@pytest.mark.asyncio
async def test_update_channel(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {"app_key": "old"},
    }, headers=headers)
    channel_id = resp.json()["id"]

    resp = await async_client.put(f"/api/channels/{channel_id}", json={
        "config": {"app_key": "new"},
        "enabled": False,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["config"]["app_key"] == "new"
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_channel(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)
    channel_id = resp.json()["id"]

    resp = await async_client.delete(f"/api/channels/{channel_id}", headers=headers)
    assert resp.status_code == 200

    # Verify deleted
    resp = await async_client.get("/api/channels", headers=headers)
    assert all(c["id"] != channel_id for c in resp.json())


@pytest.mark.asyncio
async def test_duplicate_channel_type_rejected(async_client, tenant_with_user):
    """UNIQUE(tenant_id, channel_type) constraint."""
    headers = tenant_with_user["headers"]
    await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)

    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)
    assert resp.status_code in (400, 409)
