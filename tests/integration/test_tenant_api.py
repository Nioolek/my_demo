import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_tenant(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/tenants", json={"name": "New Store"}, headers=headers)
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "New Store"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_tenants(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.get("/api/tenants", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(t["id"] == tenant_with_user["tenant_id"] for t in data)


@pytest.mark.asyncio
async def test_unauthorized_access(async_client):
    resp = await async_client.get("/api/tenants")
    assert resp.status_code == 401
