"""Integration tests for DingTalk webhook endpoint."""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.integration

DINGTALK_PAYLOAD = {
    "senderStaffId": "dt-user-001",
    "senderNick": "DingTalk User",
    "conversationType": "1",
    "conversationId": "cid-test-123",
    "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=test",
    "sessionWebhookExpiredTime": 9999999999999,
    "msgtype": "text",
    "text": {"content": "What time is it?"},
}


@pytest.mark.asyncio
async def test_dingtalk_webhook_returns_200(async_client, _init_pool):
    """Webhook should accept and ACK immediately."""
    with patch("src.api.webhooks._process_dingtalk_message", new_callable=AsyncMock) as mock_proc:
        resp = await async_client.post(
            "/webhooks/dingtalk",
            json=DINGTALK_PAYLOAD,
        )
    assert resp.status_code == 200
    assert resp.json() == {"success": True}


@pytest.mark.asyncio
async def test_dingtalk_webhook_rejects_empty_payload(async_client, _init_pool):
    resp = await async_client.post("/webhooks/dingtalk", json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_process_dingtalk_message_creates_run(_init_pool):
    """Test that processing creates a LangGraph run."""
    from src.api.webhooks import _process_dingtalk_message

    with (
        patch("src.api.webhooks._ensure_dingtalk_user", new_callable=AsyncMock) as mock_user,
        patch("src.api.webhooks._create_agent_run", new_callable=AsyncMock) as mock_run,
        patch("src.api.webhooks._send_dingtalk_reply", new_callable=AsyncMock) as mock_send,
    ):
        mock_user.return_value = "test-tenant-id"
        mock_run.return_value = "Agent response text"

        await _process_dingtalk_message(DINGTALK_PAYLOAD)

        mock_user.assert_called_once()
        mock_run.assert_called_once()
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_dingtalk_auto_provision_user(async_client, tenant_with_user, _init_pool):
    """New DingTalk user should be auto-created under a tenant with dingtalk channel."""
    from src.db.client import execute, fetch_one

    tenant_id = tenant_with_user["tenant_id"]

    # Create a dingtalk channel for this tenant (with unique config to identify it)
    await execute(
        "INSERT INTO channels (tenant_id, channel_type, config) "
        "VALUES (%s::uuid, 'dingtalk', '{\"test_auto_provision\": true}')",
        tenant_id,
    )

    # Create a DingTalk user that doesn't exist yet
    payload = {
        "senderStaffId": "new-dt-user-999",
        "senderNick": "New DT User",
        "conversationType": "1",
        "conversationId": "cid-auto-123",
        "sessionWebhook": "",
        "msgtype": "text",
        "text": {"content": "Hello"},
    }

    # Call _ensure_dingtalk_user
    from src.api.webhooks import _ensure_dingtalk_user
    result_tenant = await _ensure_dingtalk_user(payload)

    # Should find a tenant that has a dingtalk channel
    assert result_tenant, "Should find a tenant with dingtalk channel"

    # Verify user was created in DB
    user = await fetch_one(
        "SELECT id, tenant_id::text, name FROM users "
        "WHERE id = 'new-dt-user-999' AND channel_source = 'dingtalk'",
    )
    assert user is not None
    assert user["name"] == "New DT User"

    # Cleanup
    await execute("DELETE FROM users WHERE id = 'new-dt-user-999'")
    await execute("DELETE FROM channels WHERE tenant_id = %s::uuid", tenant_id)
