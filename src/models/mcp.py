"""MCP server configuration data models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MCPTransport(str, Enum):
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"
    STDIO = "stdio"


class MCPServerCreate(BaseModel):
    name: str = Field(max_length=255)
    transport: MCPTransport = MCPTransport.SSE
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class MCPServerResponse(BaseModel):
    id: UUID
    tenant_id: UUID | None = None
    name: str
    transport: MCPTransport
    url: str | None = None
    command: str | None = None
    args: list[str]
    env: dict[str, str]
    enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MCPServerUpdate(BaseModel):
    name: str | None = None
    transport: MCPTransport | None = None
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: bool | None = None