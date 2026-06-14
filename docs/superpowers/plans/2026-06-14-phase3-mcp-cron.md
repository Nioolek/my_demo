# Phase 3: MCP + Cron Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build MCP server management with dynamic tool loading and cron scheduled tasks with LangGraph native cron sync + webhook callback for proactive DingTalk push.

**Architecture:** MCP servers are configured per-tenant via CRUD API, stored in the `mcp_servers` table. At agent runtime, `load_mcp_tools()` (currently a placeholder) connects to each server via `langchain-mcp-adapters` and returns live tools. Cron jobs are managed via CRUD API that syncs with LangGraph's native cron scheduler. When a cron run completes, LangGraph calls back to `/webhooks/internal/cron-callback`, which parses the thread ID to route the response to the correct channel via ChannelManager.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, psycopg3, `langchain-mcp-adapters`, LangGraph SDK cron API, httpx.

**Reference:** Design spec at `docs/superpowers/specs/2026-06-14-multi-tenant-store-agent-design.md` Sections 7 (MCP) and 8 (Cron).

---

## File Structure

```
src/
├── models/
│   ├── mcp.py                # MCPServerCreate, MCPServerResponse, MCPServerUpdate
│   └── cron.py               # CronJobCreate, CronJobResponse, CronJobUpdate
├── api/
│   ├── mcp.py                # MCP CRUD API + test connection + list tools
│   ├── cron_jobs.py          # Cron job CRUD API + toggle + history
│   └── cron_callback.py      # /webhooks/internal/cron-callback endpoint
├── agent/
│   └── mcp_loader.py         # Real MCP tool loading (replaces placeholder in tools.py)
├── agent/tools.py            # Modify: delegate to mcp_loader
├── custom_app.py             # Register MCP, cron, and callback routers
tests/
├── unit/
│   ├── test_mcp_models.py
│   ├── test_cron_models.py
│   └── test_mcp_loader.py
├── integration/
│   ├── test_mcp_api.py
│   ├── test_cron_api.py
│   └── test_cron_callback.py
```

---

### Task 1: MCP Pydantic Models

**Files:**
- Create: `src/models/mcp.py`
- Test: `tests/unit/test_mcp_models.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_mcp_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models.mcp'`

- [ ] **Step 3: Write minimal implementation**

Create `src/models/mcp.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_mcp_models.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models/mcp.py tests/unit/test_mcp_models.py
git commit -m "feat: add MCP server Pydantic models"
```

---

### Task 2: Cron Job Pydantic Models

**Files:**
- Create: `src/models/cron.py`
- Test: `tests/unit/test_cron_models.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for cron job Pydantic models."""

import pytest
from src.models.cron import CronJobCreate, CronJobResponse, CronJobUpdate

pytestmark = pytest.mark.unit


def test_cron_create_defaults():
    body = CronJobCreate(
        name="daily-report",
        schedule="0 9 * * *",
    )
    assert body.name == "daily-report"
    assert body.schedule == "0 9 * * *"
    assert body.timezone == "Asia/Shanghai"
    assert body.description is None
    assert body.input_template is None
    assert body.enabled is True


def test_cron_create_with_template():
    body = CronJobCreate(
        name="check-inventory",
        schedule="*/30 * * * *",
        description="Check inventory every 30 min",
        input_template={"message": "Check current inventory levels"},
        timezone="UTC",
    )
    assert body.input_template["message"] == "Check current inventory levels"
    assert body.timezone == "UTC"


def test_cron_response():
    from uuid import uuid4
    from datetime import datetime, timezone

    resp = CronJobResponse(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=None,
        lg_cron_id=None,
        name="test-cron",
        description="A test job",
        schedule="0 9 * * *",
        timezone="Asia/Shanghai",
        input_template=None,
        enabled=True,
        created_by="user-1",
        created_at=datetime.now(timezone.utc),
    )
    assert resp.name == "test-cron"
    assert resp.enabled is True
    assert resp.lg_cron_id is None


def test_cron_update_partial():
    body = CronJobUpdate(enabled=False, schedule="0 10 * * *")
    assert body.enabled is False
    assert body.schedule == "0 10 * * *"
    assert body.name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_cron_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models.cron'`

- [ ] **Step 3: Write minimal implementation**

Create `src/models/cron.py`:

```python
"""Cron job configuration data models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CronJobCreate(BaseModel):
    name: str = Field(max_length=255)
    schedule: str = Field(max_length=255)
    description: str | None = None
    timezone: str = "Asia/Shanghai"
    input_template: dict | None = None
    agent_id: UUID | None = None
    enabled: bool = True


class CronJobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    agent_id: UUID | None = None
    lg_cron_id: str | None = None
    name: str
    description: str | None = None
    schedule: str
    timezone: str
    input_template: dict | None = None
    enabled: bool
    created_by: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CronJobUpdate(BaseModel):
    name: str | None = None
    schedule: str | None = None
    description: str | None = None
    timezone: str | None = None
    input_template: dict | None = None
    agent_id: UUID | None = None
    enabled: bool | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_cron_models.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models/cron.py tests/unit/test_cron_models.py
git commit -m "feat: add cron job Pydantic models"
```

---

### Task 3: MCP Tool Loader (replace placeholder)

**Files:**
- Create: `src/agent/mcp_loader.py`
- Modify: `src/agent/tools.py` (delegate `load_mcp_tools` to mcp_loader)
- Test: `tests/unit/test_mcp_loader.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_mcp_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.agent.mcp_loader'`

- [ ] **Step 3: Write minimal implementation**

Create `src/agent/mcp_loader.py`:

```python
"""MCP tool loader: connect to configured MCP servers and return LangChain tools."""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.db.client import fetch_all

logger = logging.getLogger(__name__)


async def load_mcp_tools(tenant_id: str) -> list[BaseTool]:
    """Load tools from all enabled MCP servers for a tenant.

    Connects to each server via langchain-mcp-adapters, collects all tools.
    System-level servers (tenant_id IS NULL) are included for all tenants.
    """
    rows = await fetch_all(
        "SELECT * FROM mcp_servers "
        "WHERE enabled = true AND (tenant_id = %s OR tenant_id IS NULL) "
        "ORDER BY created_at",
        tenant_id,
    )

    if not rows:
        return []

    # Build server configs for MultiServerMCPClient
    server_configs: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["name"]
        transport = row["transport"]
        config: dict[str, Any] = {"transport": transport}

        if transport == "stdio":
            config["command"] = row["command"]
            if row["args"]:
                config["args"] = row["args"]
            if row["env"]:
                config["env"] = row["env"]
        else:
            config["url"] = row["url"]

        server_configs[name] = config

    tools: list[BaseTool] = []
    try:
        async with MultiServerMCPClient(server_configs) as client:
            raw_tools = await client.get_tools()
            for t in raw_tools:
                # Prefix tool name with server name for disambiguation
                t.name = f"mcp_{name}_{t.name}"
                tools.append(t)
    except Exception:
        logger.exception("Failed to load MCP tools for tenant %s", tenant_id)

    logger.info("Loaded %d MCP tools for tenant %s", len(tools), tenant_id)
    return tools
```

- [ ] **Step 4: Modify `src/agent/tools.py` to delegate**

Replace the placeholder `load_mcp_tools` in `src/agent/tools.py`:

```python
async def load_mcp_tools(tenant_id: str) -> list[BaseTool]:
    """Load MCP tools for a tenant."""
    from src.agent.mcp_loader import load_mcp_tools as _load
    return await _load(tenant_id)
```

The existing code at lines 49-51 is:

```python
async def load_mcp_tools(tenant_id: str) -> list[BaseTool]:
    """Load MCP tools for a tenant. Placeholder for Phase 3."""
    return []
```

Replace those three lines with:

```python
async def load_mcp_tools(tenant_id: str) -> list[BaseTool]:
    """Load MCP tools for a tenant."""
    from src.agent.mcp_loader import load_mcp_tools as _load
    return await _load(tenant_id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_mcp_loader.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/agent/mcp_loader.py src/agent/tools.py tests/unit/test_mcp_loader.py
git commit -m "feat: implement MCP tool loader with langchain-mcp-adapters"
```

---

### Task 4: MCP Server CRUD API

**Files:**
- Create: `src/api/mcp.py`
- Modify: `src/custom_app.py` (register router)
- Test: `tests/integration/test_mcp_api.py`

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for MCP server CRUD API."""

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_mcp_server(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/mcp", json={
        "name": "weather-api",
        "transport": "sse",
        "url": "http://localhost:8080/sse",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "weather-api"
    assert data["transport"] == "sse"
    assert data["url"] == "http://localhost:8080/sse"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_mcp_servers(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    await async_client.post("/api/mcp", json={
        "name": "server-1",
        "transport": "sse",
        "url": "http://localhost:8081/sse",
    }, headers=headers)

    resp = await async_client.get("/api/mcp", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(s["name"] == "server-1" for s in data)


@pytest.mark.asyncio
async def test_update_mcp_server(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/mcp", json={
        "name": "old-name",
        "transport": "sse",
        "url": "http://localhost:8080/sse",
    }, headers=headers)
    server_id = resp.json()["id"]

    resp = await async_client.put(f"/api/mcp/{server_id}", json={
        "name": "new-name",
        "enabled": False,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "new-name"
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_mcp_server(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/mcp", json={
        "name": "to-delete",
        "transport": "sse",
        "url": "http://localhost:8080/sse",
    }, headers=headers)
    server_id = resp.json()["id"]

    resp = await async_client.delete(f"/api/mcp/{server_id}", headers=headers)
    assert resp.status_code == 200

    resp = await async_client.get("/api/mcp", headers=headers)
    assert all(s["id"] != server_id for s in resp.json())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/integration/test_mcp_api.py -v`
Expected: FAIL — route `/api/mcp` not found (404)

- [ ] **Step 3: Write the API implementation**

Create `src/api/mcp.py`:

```python
"""MCP server configuration CRUD API."""

import json

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.mcp import MCPServerCreate, MCPServerResponse, MCPServerUpdate

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("", response_model=list[MCPServerResponse])
async def list_mcp_servers(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM mcp_servers WHERE tenant_id = %s ORDER BY created_at",
        user["tenant_id"],
    )
    return [MCPServerResponse(**r) for r in rows]


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create_mcp_server(body: MCPServerCreate, user: dict = Depends(get_current_user)):
    row = await fetch_one(
        "INSERT INTO mcp_servers (tenant_id, name, transport, url, command, args, env, enabled) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        user["tenant_id"],
        body.name,
        body.transport.value,
        body.url,
        body.command,
        json.dumps(body.args),
        json.dumps(body.env),
        body.enabled,
    )
    return MCPServerResponse(**row)


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdate,
    user: dict = Depends(get_current_user),
):
    existing = await fetch_one(
        "SELECT * FROM mcp_servers WHERE id = %s AND tenant_id = %s",
        server_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "MCP server not found")

    updates = []
    params = []
    for field in ("name", "url", "command"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if body.transport is not None:
        updates.append("transport = %s")
        params.append(body.transport.value)
    if body.args is not None:
        updates.append("args = %s")
        params.append(json.dumps(body.args))
    if body.env is not None:
        updates.append("env = %s")
        params.append(json.dumps(body.env))
    if body.enabled is not None:
        updates.append("enabled = %s")
        params.append(body.enabled)

    if not updates:
        return MCPServerResponse(**existing)

    params.append(server_id)
    row = await fetch_one(
        f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return MCPServerResponse(**row)


@router.delete("/{server_id}")
async def delete_mcp_server(server_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT id FROM mcp_servers WHERE id = %s AND tenant_id = %s",
        server_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "MCP server not found")
    await execute("DELETE FROM mcp_servers WHERE id = %s", server_id)
    return {"detail": "Deleted"}
```

- [ ] **Step 4: Register the router in `src/custom_app.py`**

Add import:

```python
from src.api.mcp import router as mcp_router
```

Add include:

```python
app.include_router(mcp_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/integration/test_mcp_api.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/mcp.py src/custom_app.py tests/integration/test_mcp_api.py
git commit -m "feat: add MCP server CRUD API endpoints"
```

---

### Task 5: Cron Job CRUD API with LangGraph Sync

**Files:**
- Create: `src/api/cron_jobs.py`
- Modify: `src/custom_app.py` (register router)
- Test: `tests/integration/test_cron_api.py`

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for cron job CRUD API."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

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

    with patch("src.api.cron_jobs._delete_from_langgraph", new_callable=AsyncMock) as mock_del:
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

    with patch("src.api.cron_jobs._update_langgraph_cron", new_callable=AsyncMock) as mock_upd:
        resp = await async_client.post(f"/api/cron-jobs/{job_id}/toggle", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/integration/test_cron_api.py -v`
Expected: FAIL — route `/api/cron-jobs` not found (404)

- [ ] **Step 3: Write the API implementation**

Create `src/api/cron_jobs.py`:

```python
"""Cron job CRUD API with LangGraph native cron sync."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.cron import CronJobCreate, CronJobResponse, CronJobUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cron-jobs", tags=["cron-jobs"])


async def _sync_to_langgraph(
    tenant_id: str,
    user_id: str,
    name: str,
    schedule: str,
    timezone: str,
    input_template: dict | None,
) -> str:
    """Create a LangGraph native cron job and return its cron_id.

    Uses a dedicated thread per cron job for state isolation.
    The webhook callback URL routes results back to the channel.
    """
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")

    thread_id = f"{tenant_id}:{user_id}:cron:{name}"

    # Ensure thread exists
    try:
        await client.threads.get(thread_id)
    except Exception:
        await client.threads.create(thread_id=thread_id)

    cron = await client.crons.create(
        assistant_id="store-agent",
        schedule=schedule,
        input=input_template or {"messages": [{"role": "user", "content": f"Cron job: {name}"}]},
        config={"configurable": {"tenant_id": tenant_id}},
        webhook="http://127.0.0.1:2024/webhooks/internal/cron-callback",
        timezone=timezone,
    )

    return cron["cron_id"]


async def _update_langgraph_cron(
    lg_cron_id: str,
    schedule: str | None = None,
    enabled: bool | None = None,
) -> None:
    """Update a LangGraph native cron job."""
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")

    kwargs = {}
    if schedule is not None:
        kwargs["schedule"] = schedule
    if enabled is not None:
        kwargs["enabled"] = enabled

    if kwargs:
        await client.crons.update(lg_cron_id, **kwargs)


async def _delete_from_langgraph(lg_cron_id: str) -> None:
    """Delete a LangGraph native cron job."""
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")
    await client.crons.delete(lg_cron_id)


@router.get("", response_model=list[CronJobResponse])
async def list_cron_jobs(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM cron_jobs_meta WHERE tenant_id = %s ORDER BY created_at DESC",
        user["tenant_id"],
    )
    return [CronJobResponse(**r) for r in rows]


@router.post("", response_model=CronJobResponse, status_code=201)
async def create_cron_job(body: CronJobCreate, user: dict = Depends(get_current_user)):
    # Sync to LangGraph native cron
    try:
        lg_cron_id = await _sync_to_langgraph(
            tenant_id=user["tenant_id"],
            user_id=user["user_id"],
            name=body.name,
            schedule=body.schedule,
            timezone=body.timezone,
            input_template=body.input_template,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to create LangGraph cron: {e}")

    row = await fetch_one(
        "INSERT INTO cron_jobs_meta "
        "(tenant_id, agent_id, lg_cron_id, name, description, schedule, timezone, "
        " input_template, enabled, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        user["tenant_id"],
        str(body.agent_id) if body.agent_id else None,
        lg_cron_id,
        body.name,
        body.description,
        body.schedule,
        body.timezone,
        json.dumps(body.input_template) if body.input_template else None,
        body.enabled,
        user["user_id"],
    )
    return CronJobResponse(**row)


@router.put("/{job_id}", response_model=CronJobResponse)
async def update_cron_job(
    job_id: str,
    body: CronJobUpdate,
    user: dict = Depends(get_current_user),
):
    existing = await fetch_one(
        "SELECT * FROM cron_jobs_meta WHERE id = %s AND tenant_id = %s",
        job_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Cron job not found")

    updates = []
    params = []
    for field in ("name", "description", "schedule", "timezone"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if body.input_template is not None:
        updates.append("input_template = %s")
        params.append(json.dumps(body.input_template))
    if body.enabled is not None:
        updates.append("enabled = %s")
        params.append(body.enabled)
    if body.agent_id is not None:
        updates.append("agent_id = %s")
        params.append(str(body.agent_id))

    if not updates:
        return CronJobResponse(**existing)

    # Sync to LangGraph if schedule or enabled changed
    lg_cron_id = existing.get("lg_cron_id")
    if lg_cron_id and (body.schedule is not None or body.enabled is not None):
        try:
            await _update_langgraph_cron(
                lg_cron_id,
                schedule=body.schedule,
                enabled=body.enabled,
            )
        except Exception:
            logger.exception("Failed to update LangGraph cron %s", lg_cron_id)

    params.append(job_id)
    row = await fetch_one(
        f"UPDATE cron_jobs_meta SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return CronJobResponse(**row)


@router.delete("/{job_id}")
async def delete_cron_job(job_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT id, lg_cron_id FROM cron_jobs_meta WHERE id = %s AND tenant_id = %s",
        job_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Cron job not found")

    # Delete from LangGraph first
    lg_cron_id = existing.get("lg_cron_id")
    if lg_cron_id:
        try:
            await _delete_from_langgraph(lg_cron_id)
        except Exception:
            logger.exception("Failed to delete LangGraph cron %s", lg_cron_id)

    await execute("DELETE FROM cron_jobs_meta WHERE id = %s", job_id)
    return {"detail": "Deleted"}


@router.post("/{job_id}/toggle", response_model=CronJobResponse)
async def toggle_cron_job(job_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT * FROM cron_jobs_meta WHERE id = %s AND tenant_id = %s",
        job_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Cron job not found")

    new_enabled = not existing["enabled"]

    # Sync to LangGraph
    lg_cron_id = existing.get("lg_cron_id")
    if lg_cron_id:
        try:
            await _update_langgraph_cron(lg_cron_id, enabled=new_enabled)
        except Exception:
            logger.exception("Failed to toggle LangGraph cron %s", lg_cron_id)

    row = await fetch_one(
        "UPDATE cron_jobs_meta SET enabled = %s WHERE id = %s RETURNING *",
        new_enabled,
        job_id,
    )
    return CronJobResponse(**row)
```

- [ ] **Step 4: Register the router in `src/custom_app.py`**

Add import:

```python
from src.api.cron_jobs import router as cron_jobs_router
```

Add include:

```python
app.include_router(cron_jobs_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/integration/test_cron_api.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/cron_jobs.py src/custom_app.py tests/integration/test_cron_api.py
git commit -m "feat: add cron job CRUD API with LangGraph native sync"
```

---

### Task 6: Cron Webhook Callback

**Files:**
- Create: `src/api/cron_callback.py`
- Modify: `src/custom_app.py` (register router)
- Test: `tests/integration/test_cron_callback.py`

- [ ] **Step 1: Write the failing test**

```python
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
    with (
        patch("src.api.cron_callback.ChannelManager") as mock_mgr_cls,
        patch("src.api.cron_callback._get_last_ai_message", return_value="Report ready!"),
    ):
        mock_mgr = AsyncMock()
        mock_mgr.send = AsyncMock()
        mock_mgr_cls.return_value = mock_mgr

        resp = await async_client.post(
            "/webhooks/internal/cron-callback",
            json=CRON_CALLBACK_PAYLOAD,
        )
        assert resp.status_code == 200
        assert resp.json() == {"success": True}


@pytest.mark.asyncio
async def test_cron_callback_parses_thread_id(async_client, _init_pool):
    """Callback parses thread_id and routes via ChannelManager."""
    with (
        patch("src.api.cron_callback.ChannelManager") as mock_mgr_cls,
        patch("src.api.cron_callback._get_last_ai_message", return_value="Your daily summary."),
    ):
        mock_mgr = AsyncMock()
        mock_mgr.send = AsyncMock()
        mock_mgr_cls.return_value = mock_mgr

        await async_client.post(
            "/webhooks/internal/cron-callback",
            json=CRON_CALLBACK_PAYLOAD,
        )

        mock_mgr.send.assert_called_once()
        call_args = mock_mgr.send.call_args
        assert call_args[0][0] == "dingtalk"
        assert "Your daily summary" in str(call_args[1])


@pytest.mark.asyncio
async def test_cron_callback_missing_thread_id(async_client, _init_pool):
    resp = await async_client.post(
        "/webhooks/internal/cron-callback",
        json={"run_id": "x", "status": "success"},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/integration/test_cron_callback.py -v`
Expected: FAIL — route `/webhooks/internal/cron-callback` not found (404)

- [ ] **Step 3: Write the callback endpoint**

Create `src/api/cron_callback.py`:

```python
"""Cron webhook callback: receives run completions from LangGraph and routes to channels."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.channels.base import parse_thread_id
from src.channels.manager import ChannelManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cron-callback"])

_channel_manager = ChannelManager()


def _get_last_ai_message(payload: dict[str, Any]) -> str:
    """Extract the last AI message from cron callback payload outputs."""
    outputs = payload.get("outputs", {})
    messages = outputs.get("messages", [])
    for msg in reversed(messages):
        if msg.get("type") == "ai" and msg.get("content"):
            return msg["content"]
    return "Cron job completed."


@router.post("/webhooks/internal/cron-callback")
async def cron_callback(request: Request):
    """Receive LangGraph cron run completion callbacks.

    Parses the thread_id to extract routing info, extracts the agent's
    final response, and routes it to the correct channel via ChannelManager.
    """
    payload = await request.json()

    thread_id = payload.get("thread_id")
    if not thread_id:
        raise HTTPException(400, "Missing thread_id")

    # Parse routing info from thread_id
    try:
        tenant_id, user_id, channel, session_id = parse_thread_id(thread_id)
    except ValueError:
        logger.warning("Invalid thread_id in cron callback: %s", thread_id)
        raise HTTPException(400, "Invalid thread_id format")

    # Extract agent's response
    response_text = _get_last_ai_message(payload)

    # Route to channel
    try:
        await _channel_manager.send(
            channel_type=channel,
            to_handle=user_id,
            text=response_text,
            meta={"source": "cron", "run_id": payload.get("run_id")},
        )
    except ValueError:
        logger.warning("Unknown channel '%s' in cron callback", channel)

    logger.info(
        "Cron callback processed: tenant=%s user=%s channel=%s run=%s",
        tenant_id, user_id, channel, payload.get("run_id"),
    )
    return {"success": True}
```

- [ ] **Step 4: Register the router in `src/custom_app.py`**

Add import:

```python
from src.api.cron_callback import router as cron_callback_router
```

Add include:

```python
app.include_router(cron_callback_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/integration/test_cron_callback.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/cron_callback.py src/custom_app.py tests/integration/test_cron_callback.py
git commit -m "feat: add cron webhook callback with channel routing"
```

---

### Task 7: Run Full Test Suite + Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (existing ~65 + new Phase 3 tests)

- [ ] **Step 2: Verify imports and module loading**

Run: `.venv/Scripts/python -c "from src.models.mcp import MCPServerCreate; from src.models.cron import CronJobCreate; from src.agent.mcp_loader import load_mcp_tools; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 3: Commit any remaining changes and push**

```bash
git push origin main
```

---

## Self-Review Checklist

**1. Spec coverage:**
- MCP server management + dynamic tool loading: Tasks 1, 3, 4
- Cron scheduled tasks (LangGraph native + webhook callback): Tasks 2, 5, 6
- Cron → DingTalk proactive push: Task 6 (cron_callback routes via ChannelManager)
- API endpoints per design spec:
  - `/api/mcp` GET/POST/PUT/DELETE: Task 4
  - `/api/cron-jobs` GET/POST/PUT/DELETE + toggle: Task 5
  - `/webhooks/internal/cron-callback`: Task 6

**2. Placeholder scan:** No TODOs, TBDs, or placeholders found.

**3. Type consistency:**
- `MCPServerCreate`, `MCPServerResponse`, `MCPServerUpdate` used consistently across Task 1 (models) and Task 4 (API)
- `CronJobCreate`, `CronJobResponse`, `CronJobUpdate` used consistently across Task 2 (models) and Task 5 (API)
- `parse_thread_id` from `src.channels.base` used in Task 6 (cron callback)
- `ChannelManager` from `src.channels.manager` used in Task 6 (cron callback)
- `load_mcp_tools` signature `(tenant_id: str) -> list[BaseTool]` consistent between Task 3 (loader) and Task 3 (tools.py delegation)
