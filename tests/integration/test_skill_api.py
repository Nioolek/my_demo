import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.integration


@pytest.fixture
def setup_tenant():
    import asyncio
    from src.auth import create_token
    from src.db.client import execute
    import uuid

    tenant_id = str(uuid.uuid4())

    async def _setup():
        await execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", tenant_id, "Skill Test Store")
        await execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES (%s,%s,%s,%s,%s)",
            "skill-mgr", tenant_id, "Manager", "manager", "console"
        )
        await execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES (%s,%s,%s,%s,%s)",
            "skill-admin", tenant_id, "Admin", "admin", "console"
        )

    asyncio.get_event_loop().run_until_complete(_setup())

    mgr_token = create_token("skill-mgr", tenant_id)
    admin_token = create_token("skill-admin", tenant_id)

    yield {
        "tenant_id": tenant_id,
        "mgr_headers": {"authorization": f"Bearer {mgr_token}"},
        "admin_headers": {"authorization": f"Bearer {admin_token}"},
    }

    async def _cleanup():
        await execute("DELETE FROM skills_meta WHERE tenant_id = %s", tenant_id)
        await execute("DELETE FROM users WHERE tenant_id = %s", tenant_id)
        await execute("DELETE FROM tenants WHERE id = %s", tenant_id)

    asyncio.get_event_loop().run_until_complete(_cleanup())


@pytest.fixture
def client():
    from src.custom_app import app
    from starlette.testclient import TestClient
    return TestClient(app)


def test_create_skill(client, setup_tenant):
    headers = setup_tenant["mgr_headers"]
    resp = client.post("/api/skills", json={
        "name": "test-skill",
        "content": "---\nname: test-skill\ndescription: Test\n---\n# Test Skill",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-skill"
    assert data["status"] == "draft"


def test_skill_approval_workflow(client, setup_tenant):
    mgr = setup_tenant["mgr_headers"]
    admin = setup_tenant["admin_headers"]

    resp = client.post("/api/skills", json={
        "name": "approval-test",
        "content": "---\nname: approval-test\ndescription: Approval test\n---\n# Test",
    }, headers=mgr)
    assert resp.status_code == 201
    skill_id = resp.json()["id"]

    resp = client.post(f"/api/skills/{skill_id}/submit", headers=mgr)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    resp = client.post(f"/api/skills/{skill_id}/approve", headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_skill_rejection(client, setup_tenant):
    mgr = setup_tenant["mgr_headers"]
    admin = setup_tenant["admin_headers"]

    resp = client.post("/api/skills", json={
        "name": "reject-test",
        "content": "---\nname: reject-test\ndescription: Will be rejected\n---\n# Test",
    }, headers=mgr)
    skill_id = resp.json()["id"]

    client.post(f"/api/skills/{skill_id}/submit", headers=mgr)

    resp = client.post(f"/api/skills/{skill_id}/reject", json={
        "rejection_reason": "Not relevant"
    }, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["rejection_reason"] == "Not relevant"


def test_list_pending_skills(client, setup_tenant):
    mgr = setup_tenant["mgr_headers"]
    admin = setup_tenant["admin_headers"]

    client.post("/api/skills", json={
        "name": "pending-list-test",
        "content": "---\nname: pending-list-test\ndescription: test\n---\n# Test",
    }, headers=mgr)

    resp = client.get("/api/skills/pending", headers=admin)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
