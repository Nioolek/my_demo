"""Integration tests for cron webhook callback."""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.integration

CRON_CALLBACK_PAYLOAD = {
    "thread_id": "tenant-1:user-2:dingtalk:cid-123",
    "run_id": "run-abc-456",
    "status": "success",
    "outputs": {
        "messages": [
            {"type": "ai", "content": "Daily report: All metrics normal."},
        ],
    },
}


@pytest.mark.asyncio
async def test_cron_callback_returns_200(async_client, _init_pool):
    """Callback should accept and process immediately."""
    with patch("src.api.cron_callback._channel_manager") as mock_mgr:
        mock_mgr.send = AsyncMock()

        resp = await async_client.post(
            "/webhooks/internal/cron-callback",
            json=CRON_CALLBACK_PAYLOAD,
        )
        assert resp.status_code == 200
        assert resp.json() == {"success": True}


@pytest.mark.asyncio
async def test_cron_callback_parses_thread_id(async_client, _init_pool):
    """Callback parses thread_id and routes via ChannelManager."""
    with patch("src.api.cron_callback._channel_manager") as mock_mgr:
        mock_mgr.send = AsyncMock()

        await async_client.post(
            "/webhooks/internal/cron-callback",
            json=CRON_CALLBACK_PAYLOAD,
        )

        mock_mgr.send.assert_called_once()
        # Verify channel_type is "dingtalk" (keyword arg)
        call = mock_mgr.send.call_args
        assert call.kwargs["channel_type"] == "dingtalk"


@pytest.mark.asyncio
async def test_cron_callback_missing_thread_id(async_client, _init_pool):
    resp = await async_client.post(
        "/webhooks/internal/cron-callback",
        json={"run_id": "x", "status": "success"},
    )
    assert resp.status_code == 400
