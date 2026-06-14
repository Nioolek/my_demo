import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_skill(async_client, tenant_with_admin):
    headers = tenant_with_admin["mgr_headers"]
    resp = await async_client.post("/api/skills", json={
        "name": "test-skill",
        "content": "---\nname: test-skill\ndescription: Test\n---\n# Test Skill",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-skill"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_skill_approval_workflow(async_client, tenant_with_admin):
    mgr = tenant_with_admin["mgr_headers"]
    admin = tenant_with_admin["admin_headers"]

    resp = await async_client.post("/api/skills", json={
        "name": "approval-test",
        "content": "---\nname: approval-test\ndescription: Approval test\n---\n# Test",
    }, headers=mgr)
    assert resp.status_code == 201
    skill_id = resp.json()["id"]

    resp = await async_client.post(f"/api/skills/{skill_id}/submit", headers=mgr)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    resp = await async_client.post(f"/api/skills/{skill_id}/approve", headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_skill_rejection(async_client, tenant_with_admin):
    mgr = tenant_with_admin["mgr_headers"]
    admin = tenant_with_admin["admin_headers"]

    resp = await async_client.post("/api/skills", json={
        "name": "reject-test",
        "content": "---\nname: reject-test\ndescription: Will be rejected\n---\n# Test",
    }, headers=mgr)
    skill_id = resp.json()["id"]

    await async_client.post(f"/api/skills/{skill_id}/submit", headers=mgr)

    resp = await async_client.post(f"/api/skills/{skill_id}/reject", json={
        "approved": False,
        "rejection_reason": "Not relevant",
    }, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["rejection_reason"] == "Not relevant"


@pytest.mark.asyncio
async def test_list_pending_skills(async_client, tenant_with_admin):
    mgr = tenant_with_admin["mgr_headers"]
    admin = tenant_with_admin["admin_headers"]

    await async_client.post("/api/skills", json={
        "name": "pending-list-test",
        "content": "---\nname: pending-list-test\ndescription: test\n---\n# Test",
    }, headers=mgr)

    resp = await async_client.get("/api/skills/pending", headers=admin)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
