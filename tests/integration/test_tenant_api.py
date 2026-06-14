import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.integration


@pytest.fixture
def app():
    from src.custom_app import app
    return app


@pytest.fixture
def client(app):
    from starlette.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def auth_headers():
    import asyncio
    from src.auth import create_token
    from src.db.client import execute
    import uuid

    tenant_id = str(uuid.uuid4())
    asyncio.get_event_loop().run_until_complete(
        execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", tenant_id, "API Test Store")
    )
    asyncio.get_event_loop().run_until_complete(
        execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) "
            "VALUES (%s, %s, %s, %s, %s)",
            "api-test-user", tenant_id, "API Tester", "manager", "console"
        )
    )
    token = create_token("api-test-user", tenant_id)
    yield {"authorization": f"Bearer {token}"}, tenant_id
    asyncio.get_event_loop().run_until_complete(
        execute("DELETE FROM users WHERE id = %s", "api-test-user")
    )
    asyncio.get_event_loop().run_until_complete(
        execute("DELETE FROM tenants WHERE id = %s", tenant_id)
    )


def test_create_tenant(client, auth_headers):
    headers, _ = auth_headers
    resp = client.post("/api/tenants", json={"name": "New Store"}, headers=headers)
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "New Store"
    assert "id" in data


def test_list_tenants(client, auth_headers):
    headers, tenant_id = auth_headers
    resp = client.get("/api/tenants", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(t["id"] == tenant_id for t in data)


def test_unauthorized_access(client):
    resp = client.get("/api/tenants")
    assert resp.status_code == 401
