import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.integration


@pytest.fixture
def setup():
    import asyncio
    from src.auth import create_token
    from src.db.client import execute
    import uuid

    tenant_id = str(uuid.uuid4())

    async def _setup():
        await execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", tenant_id, "Agent Test")
        await execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES (%s,%s,%s,%s,%s)",
            "agent-user", tenant_id, "User", "manager", "console"
        )

    asyncio.get_event_loop().run_until_complete(_setup())
    token = create_token("agent-user", tenant_id)
    yield {"authorization": f"Bearer {token}"}, tenant_id

    async def _cleanup():
        await execute("DELETE FROM agents WHERE tenant_id = %s", tenant_id)
        await execute("DELETE FROM users WHERE tenant_id = %s", tenant_id)
        await execute("DELETE FROM tenants WHERE id = %s", tenant_id)

    asyncio.get_event_loop().run_until_complete(_cleanup())


@pytest.fixture
def client():
    from src.custom_app import app
    from starlette.testclient import TestClient
    return TestClient(app)


def test_create_agent(client, setup):
    headers, _ = setup
    resp = client.post("/api/agents", json={
        "name": "store-helper",
        "model": "gpt-4o",
        "system_prompt": "You help with store operations.",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "store-helper"


def test_get_agent(client, setup):
    headers, _ = setup
    resp = client.post("/api/agents", json={"name": "get-test"}, headers=headers)
    agent_id = resp.json()["id"]
    resp = client.get(f"/api/agents/{agent_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-test"


def test_update_agent(client, setup):
    headers, _ = setup
    resp = client.post("/api/agents", json={"name": "update-test"}, headers=headers)
    agent_id = resp.json()["id"]
    resp = client.put(f"/api/agents/{agent_id}", json={
        "system_prompt": "Updated prompt",
        "temperature": 0.5,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["system_prompt"] == "Updated prompt"
    assert resp.json()["temperature"] == 0.5
