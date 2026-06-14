"""Unit tests for ChannelManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.channels.manager import ChannelManager

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_register_and_get_channel():
    manager = ChannelManager()
    mock_channel = MagicMock()
    mock_channel.channel = "dingtalk"

    manager.register(mock_channel)
    retrieved = manager.get("dingtalk")
    assert retrieved is mock_channel


def test_get_unknown_channel_returns_none():
    manager = ChannelManager()
    assert manager.get("unknown") is None


@pytest.mark.asyncio
async def test_send_routes_to_correct_channel():
    manager = ChannelManager()
    mock_channel = MagicMock()
    mock_channel.channel = "dingtalk"
    mock_channel.send = AsyncMock()

    manager.register(mock_channel)
    await manager.send("dingtalk", "https://webhook.url", "Hello!", {"source": "test"})

    mock_channel.send.assert_called_once_with(
        "https://webhook.url", "Hello!", {"source": "test"}
    )


@pytest.mark.asyncio
async def test_send_unknown_channel_raises():
    manager = ChannelManager()
    with pytest.raises(ValueError, match="Unknown channel"):
        await manager.send("unknown", "handle", "text")
