import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_agent(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/agents", json={
        "name": "store-helper",
        "model": "gpt-4o",
        "system_prompt": "You help with store operations.",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "store-helper"


@pytest.mark.asyncio
async def test_get_agent(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/agents", json={"name": "get-test"}, headers=headers)
    agent_id = resp.json()["id"]
    resp = await async_client.get(f"/api/agents/{agent_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-test"


@pytest.mark.asyncio
async def test_update_agent(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/agents", json={"name": "update-test"}, headers=headers)
    agent_id = resp.json()["id"]
    resp = await async_client.put(f"/api/agents/{agent_id}", json={
        "system_prompt": "Updated prompt",
        "temperature": 0.5,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["system_prompt"] == "Updated prompt"
    assert resp.json()["temperature"] == 0.5
