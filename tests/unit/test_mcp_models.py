"""Unit tests for MCP server Pydantic models."""

import pytest
from src.models.mcp import MCPTransport, MCPServerCreate, MCPServerResponse, MCPServerUpdate

pytestmark = pytest.mark.unit


def test_transport_values():
    assert MCPTransport.SSE.value == "sse"
    assert MCPTransport.STREAMABLE_HTTP.value == "streamable_http"
    assert MCPTransport.STDIO.value == "stdio"


def test_mcp_create_defaults():
    body = MCPServerCreate(name="weather-api", transport=MCPTransport.SSE, url="http://localhost:8080/sse")
    assert body.name == "weather-api"
    assert body.transport == MCPTransport.SSE
    assert body.args == []
    assert body.env == {}
    assert body.enabled is True


def test_mcp_create_stdio():
    body = MCPServerCreate(
        name="local-tool",
        transport=MCPTransport.STDIO,
        command="python",
        args=["-m", "my_mcp_server"],
        env={"DEBUG": "1"},
    )
    assert body.command == "python"
    assert body.args == ["-m", "my_mcp_server"]
    assert body.env["DEBUG"] == "1"


def test_mcp_create_invalid_transport():
    with pytest.raises(Exception):
        MCPServerCreate(name="bad", transport="grpc")


def test_mcp_response():
    from uuid import uuid4
    from datetime import datetime, timezone

    resp = MCPServerResponse(
        id=uuid4(),
        tenant_id=uuid4(),
        name="test-server",
        transport=MCPTransport.SSE,
        url="http://example.com/sse",
        command=None,
        args=[],
        env={},
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.transport == MCPTransport.SSE
    assert resp.enabled is True


def test_mcp_update_partial():
    body = MCPServerUpdate(enabled=False)
    assert body.enabled is False
    assert body.name is None
    assert body.url is None
