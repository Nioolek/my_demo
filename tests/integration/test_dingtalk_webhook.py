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
