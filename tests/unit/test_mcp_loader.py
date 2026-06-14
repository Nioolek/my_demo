"""Unit tests for MCP tool loader."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agent.mcp_loader import load_mcp_tools

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_load_mcp_tools_no_servers():
    """Returns empty list when no MCP servers configured."""
    with patch("src.agent.mcp_loader.fetch_all", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []
        tools = await load_mcp_tools("tenant-1")
        assert tools == []


@pytest.mark.asyncio
async def test_load_mcp_tools_skips_disabled():
    """Skips servers with enabled=False."""
    with patch("src.agent.mcp_loader.fetch_all", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {"id": "id-1", "name": "s1", "transport": "sse", "url": "http://x",
             "command": None, "args": [], "env": {}, "enabled": False},
        ]
        tools = await load_mcp_tools("tenant-1")
        assert tools == []


@pytest.mark.asyncio
async def test_load_mcp_tools_sse_client():
    """Creates SSE client for sse transport."""
    mock_tools = [MagicMock(), MagicMock()]
    mock_tools[0].name = "tool_a"
    mock_tools[1].name = "tool_b"

    with (
        patch("src.agent.mcp_loader.fetch_all", new_callable=AsyncMock) as mock_fetch,
        patch("src.agent.mcp_loader.MultiServerMCPClient") as mock_multi,
    ):
        mock_fetch.return_value = [
            {"id": "id-1", "name": "weather", "transport": "sse",
             "url": "http://localhost:8080/sse", "command": None,
             "args": [], "env": {}, "enabled": True},
        ]

        mock_client = MagicMock()
        mock_client.get_tools = AsyncMock(return_value=mock_tools)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_multi.return_value = mock_client

        tools = await load_mcp_tools("tenant-1")

        assert len(tools) == 2
        mock_multi.assert_called_once()
        # Verify server config was passed correctly
        call_args = mock_multi.call_args[0][0]
        assert "weather" in call_args
        assert call_args["weather"]["transport"] == "sse"
        assert call_args["weather"]["url"] == "http://localhost:8080/sse"
