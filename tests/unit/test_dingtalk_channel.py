"""Unit tests for DingTalkChannel."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.channels.dingtalk import DingTalkChannel

pytestmark = pytest.mark.unit


def test_parse_incoming_text_message():
    ch = DingTalkChannel()
    payload = {
        "senderStaffId": "staff-001",
        "senderNick": "Zhang Wei",
        "conversationType": "1",
        "conversationId": "cid-123",
        "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=abc",
        "msgtype": "text",
        "text": {"content": "  Hello store agent  "},
    }
    msg = ch.parse_incoming(payload)
    assert msg.user_id == "staff-001"
    assert msg.content == "Hello store agent"
    assert msg.channel == "dingtalk"
    assert msg.meta["sender_name"] == "Zhang Wei"
    assert msg.meta["conversation_type"] == "1"
    assert "session_webhook" in msg.meta


def test_parse_incoming_strips_at_bot():
    ch = DingTalkChannel()
    payload = {
        "senderStaffId": "staff-002",
        "conversationType": "2",
        "conversationId": "cid-456",
        "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=def",
        "msgtype": "text",
        "text": {"content": "@StoreBot help me check inventory"},
    }
    msg = ch.parse_incoming(payload)
    assert msg.content == "help me check inventory"


def test_parse_incoming_empty_content():
    ch = DingTalkChannel()
    payload = {
        "senderStaffId": "staff-003",
        "conversationType": "1",
        "conversationId": "cid-789",
        "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=ghi",
        "msgtype": "text",
        "text": {"content": "  "},
    }
    msg = ch.parse_incoming(payload)
    assert msg.content == ""


@pytest.mark.asyncio
async def test_send_via_session_webhook():
    ch = DingTalkChannel()
    mock_post = AsyncMock()
    mock_post.return_value = MagicMock(status_code=200)

    with patch("src.channels.dingtalk.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await ch.send(
            to_handle="https://oapi.dingtalk.com/robot/sendBySession?session=abc",
            text="Hello from agent!",
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs[0][0] == "https://oapi.dingtalk.com/robot/sendBySession?session=abc"


@pytest.mark.asyncio
async def test_start_and_stop():
    ch = DingTalkChannel()
    await ch.start()
    await ch.stop()
