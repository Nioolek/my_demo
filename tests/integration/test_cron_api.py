"""Integration tests for cron job CRUD API."""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_cron_job(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]

    with patch("src.api.cron_jobs._sync_to_langgraph", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = "lg-cron-abc123"
        resp = await async_client.post("/api/cron-jobs", json={
            "name": "daily-report",
            "schedule": "0 9 * * *",
            "description": "Daily sales report",
        }, headers=headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "daily-report"
    assert data["schedule"] == "0 9 * * *"
    assert data["lg_cron_id"] == "lg-cron-abc123"


@pytest.mark.asyncio
async def test_list_cron_jobs(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    with patch("src.api.cron_jobs._sync_to_langgraph", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = "lg-xyz"
        await async_client.post("/api/cron-jobs", json={
            "name": "job-1",
            "schedule": "* * * * *",
        }, headers=headers)

    resp = await async_client.get("/api/cron-jobs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(j["name"] == "job-1" for j in data)


@pytest.mark.asyncio
async def test_delete_cron_job(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    with patch("src.api.cron_jobs._sync_to_langgraph", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = "lg-del-1"
        resp = await async_client.post("/api/cron-jobs", json={
            "name": "to-delete",
            "schedule": "* * * * *",
        }, headers=headers)
        job_id = resp.json()["id"]

    with patch("src.api.cron_jobs._delete_from_langgraph", new_callable=AsyncMock):
        resp = await async_client.delete(f"/api/cron-jobs/{job_id}", headers=headers)
        assert resp.status_code == 200

    resp = await async_client.get("/api/cron-jobs", headers=headers)
    assert all(j["id"] != job_id for j in resp.json())


@pytest.mark.asyncio
async def test_toggle_cron_job(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    with patch("src.api.cron_jobs._sync_to_langgraph", new_callable=AsyncMock) as mock_sync:
        mock_sync.return_value = "lg-toggle-1"
        resp = await async_client.post("/api/cron-jobs", json={
            "name": "toggle-me",
            "schedule": "* * * * *",
        }, headers=headers)
        job_id = resp.json()["id"]

    with patch("src.api.cron_jobs._update_langgraph_cron", new_callable=AsyncMock):
        resp = await async_client.post(f"/api/cron-jobs/{job_id}/toggle", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
