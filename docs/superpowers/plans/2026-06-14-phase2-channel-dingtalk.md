# Phase 2: Channel + DingTalk Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the channel abstraction layer with DingTalk integration, enabling end-to-end message flow: DingTalk message → Agent → DingTalk reply.

**Architecture:** A simplified `BaseChannel` ABC defines the channel contract (`send`, `parse_incoming`, `process_message`). `DingTalkChannel` receives HTTP webhook callbacks, parses DingTalk payloads into `IncomingMessage` dataclasses, creates LangGraph runs via `langgraph_sdk`, and sends responses back via DingTalk session webhook. `ChannelManager` provides centralized outbound routing. Channel CRUD APIs manage per-tenant channel configuration. Thread metadata tracks conversations across channels.

**Tech Stack:** Python 3.13, LangGraph SDK (`langgraph_sdk`), httpx (async HTTP), FastAPI, Pydantic v2, psycopg3, DingTalk HTTP webhook API.

**Reference:** Design spec at `docs/superpowers/specs/2026-06-14-multi-tenant-store-agent-design.md` Section 6 (Channel Layer). QwenPaw DingTalk reference at `CoPaw_fork/src/qwenpaw/app/channels/dingtalk/`.

---

## File Structure

```
src/
├── channels/
│   ├── __init__.py          # Package init, re-exports
│   ├── base.py              # BaseChannel ABC + IncomingMessage dataclass
│   ├── dingtalk.py           # DingTalkChannel implementation
│   └── manager.py            # ChannelManager for outbound routing
├── models/
│   └── channel.py            # ChannelCreate, ChannelResponse, ChannelUpdate
├── api/
│   └── channels.py           # Channel CRUD API routes
├── db/
│   └── migrations/
│       └── 002_threads_meta.sql  # Ensure threads_meta table exists
├── custom_app.py             # Register channel routes + webhook endpoints
tests/
├── unit/
│   ├── test_channel_base.py      # BaseChannel interface tests
│   └── test_channel_models.py    # Channel Pydantic model tests
├── integration/
│   ├── test_channel_api.py       # Channel CRUD API tests
│   └── test_dingtalk_webhook.py  # DingTalk webhook endpoint tests
```

---

### Task 1: Channel Pydantic Models

**Files:**
- Create: `src/models/channel.py`
- Test: `tests/unit/test_channel_models.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for channel Pydantic models."""

import pytest
from src.models.channel import (
    ChannelType,
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
)

pytestmark = pytest.mark.unit


def test_channel_type_values():
    assert ChannelType.DINGTALK.value == "dingtalk"
    assert ChannelType.CONSOLE.value == "console"


def test_channel_create_defaults():
    body = ChannelCreate(channel_type=ChannelType.DINGTALK)
    assert body.channel_type == ChannelType.DINGTALK
    assert body.config == {}
    assert body.enabled is True


def test_channel_create_with_config():
    body = ChannelCreate(
        channel_type=ChannelType.DINGTALK,
        config={"app_key": "test-key", "app_secret": "test-secret"},
        enabled=True,
    )
    assert body.config["app_key"] == "test-key"


def test_channel_create_invalid_type():
    with pytest.raises(Exception):
        ChannelCreate(channel_type="invalid_type")


def test_channel_response():
    from uuid import uuid4
    from datetime import datetime, timezone

    resp = ChannelResponse(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=None,
        channel_type=ChannelType.DINGTALK,
        config={"app_key": "test"},
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.channel_type == ChannelType.DINGTALK
    assert resp.enabled is True


def test_channel_update_partial():
    body = ChannelUpdate(enabled=False)
    assert body.enabled is False
    assert body.config is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_channel_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.models.channel'`

- [ ] **Step 3: Write minimal implementation**

Create `src/models/channel.py`:

```python
"""Channel configuration data models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    DINGTALK = "dingtalk"
    CONSOLE = "console"


class ChannelCreate(BaseModel):
    channel_type: ChannelType
    config: dict = Field(default_factory=dict)
    enabled: bool = True


class ChannelResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    agent_id: UUID | None = None
    channel_type: ChannelType
    config: dict
    enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelUpdate(BaseModel):
    config: dict | None = None
    enabled: bool | None = None
    agent_id: UUID | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_channel_models.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/models/channel.py tests/unit/test_channel_models.py
git commit -m "feat: add channel Pydantic models"
```

---

### Task 2: BaseChannel ABC and IncomingMessage

**Files:**
- Create: `src/channels/__init__.py`
- Create: `src/channels/base.py`
- Test: `tests/unit/test_channel_base.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for BaseChannel ABC and IncomingMessage."""

import pytest
from dataclasses import dataclass
from src.channels.base import BaseChannel, IncomingMessage

pytestmark = pytest.mark.unit


def test_incoming_message_fields():
    msg = IncomingMessage(
        user_id="user-123",
        tenant_id="tenant-456",
        content="Hello",
        session_id="session-789",
        channel="dingtalk",
        meta={"sender_name": "Test User"},
    )
    assert msg.user_id == "user-123"
    assert msg.tenant_id == "tenant-456"
    assert msg.content == "Hello"
    assert msg.session_id == "session-789"
    assert msg.channel == "dingtalk"
    assert msg.meta["sender_name"] == "Test User"


def test_incoming_message_defaults():
    msg = IncomingMessage(
        user_id="u1",
        tenant_id="t1",
        content="hi",
    )
    assert msg.session_id == ""
    assert msg.channel == ""
    assert msg.meta == {}


def test_build_thread_id():
    from src.channels.base import build_thread_id

    tid = build_thread_id("tenant-1", "user-2", "dingtalk", "sess-3")
    assert tid == "tenant-1:user-2:dingtalk:sess-3"


def test_parse_thread_id():
    from src.channels.base import parse_thread_id

    tenant_id, user_id, channel, session_id = parse_thread_id(
        "tenant-1:user-2:dingtalk:sess-3"
    )
    assert tenant_id == "tenant-1"
    assert user_id == "user-2"
    assert channel == "dingtalk"
    assert session_id == "sess-3"


def test_parse_thread_id_invalid():
    from src.channels.base import parse_thread_id

    with pytest.raises(ValueError):
        parse_thread_id("invalid-thread-id")


class ConcreteChannel(BaseChannel):
    """Concrete implementation for testing."""

    channel = "test"

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send(self, to_handle: str, text: str, meta: dict | None = None):
        pass

    def parse_incoming(self, payload: dict) -> IncomingMessage:
        return IncomingMessage(
            user_id=payload["user_id"],
            tenant_id=payload["tenant_id"],
            content=payload["content"],
        )


@pytest.mark.asyncio
async def test_concrete_channel_parse_incoming():
    ch = ConcreteChannel()
    msg = ch.parse_incoming({
        "user_id": "u1",
        "tenant_id": "t1",
        "content": "test message",
    })
    assert msg.user_id == "u1"
    assert msg.content == "test message"


def test_base_channel_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseChannel()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_channel_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.channels'`

- [ ] **Step 3: Write minimal implementation**

Create `src/channels/__init__.py`:

```python
"""Channel abstraction layer."""
```

Create `src/channels/base.py`:

```python
"""BaseChannel ABC and message routing utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IncomingMessage:
    """Parsed incoming message from any channel."""

    user_id: str
    tenant_id: str
    content: str
    session_id: str = ""
    channel: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def build_thread_id(
    tenant_id: str, user_id: str, channel: str, session_id: str
) -> str:
    """Build a globally unique thread ID encoding routing info."""
    return f"{tenant_id}:{user_id}:{channel}:{session_id}"


def parse_thread_id(thread_id: str) -> tuple[str, str, str, str]:
    """Parse a thread ID into (tenant_id, user_id, channel, session_id).

    Raises:
        ValueError: If the thread_id format is invalid.
    """
    parts = thread_id.split(":", 3)
    if len(parts) != 4:
        raise ValueError(
            f"Invalid thread_id format: expected 4 colon-separated parts, "
            f"got {len(parts)}"
        )
    return parts[0], parts[1], parts[2], parts[3]


class BaseChannel(ABC):
    """Abstract base class for all channels.

    Subclasses must implement: start, stop, send, parse_incoming.
    """

    channel: str

    @abstractmethod
    async def start(self) -> None:
        """Initialize the channel (connect, register handlers)."""

    @abstractmethod
    async def stop(self) -> None:
        """Shut down the channel."""

    @abstractmethod
    async def send(
        self,
        to_handle: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Send a text message to a user/conversation.

        Args:
            to_handle: Routing handle (e.g., session webhook URL).
            text: Message text to send.
            meta: Optional metadata (source, run_id, etc.).
        """

    @abstractmethod
    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage:
        """Parse a raw channel payload into an IncomingMessage.

        Args:
            payload: Raw dict from the channel's webhook/callback.

        Returns:
            Parsed IncomingMessage.
        """
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_channel_base.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/channels/__init__.py src/channels/base.py tests/unit/test_channel_base.py
git commit -m "feat: add BaseChannel ABC and thread ID utilities"
```

---

### Task 3: DingTalk Channel Implementation

**Files:**
- Create: `src/channels/dingtalk.py`
- Test: `tests/unit/test_dingtalk_channel.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_dingtalk_channel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.channels.dingtalk'`

- [ ] **Step 3: Write minimal implementation**

Create `src/channels/dingtalk.py`:

```python
"""DingTalk channel implementation.

Receives messages via HTTP webhook callback, sends responses via
DingTalk session webhook URL.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from src.channels.base import BaseChannel, IncomingMessage

logger = logging.getLogger(__name__)

# Pattern to strip @bot mention prefix from message text
_AT_BOT_PATTERN = re.compile(r"^@\S+\s*")


class DingTalkChannel(BaseChannel):
    """DingTalk channel: HTTP webhook → LangGraph run → session webhook reply."""

    channel = "dingtalk"

    async def start(self) -> None:
        """No persistent connection needed for HTTP webhook mode."""

    async def stop(self) -> None:
        """No cleanup needed for HTTP webhook mode."""

    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage:
        """Parse DingTalk robot callback payload into IncomingMessage.

        DingTalk robot callback payload structure:
        {
            "senderStaffId": "...",     # user's staff ID
            "senderNick": "...",         # display name
            "conversationType": "1|2",  # 1=private, 2=group
            "conversationId": "...",
            "sessionWebhook": "https://...",
            "msgtype": "text",
            "text": {"content": "..."},
        }
        """
        user_id = payload.get("senderStaffId", "")
        sender_name = payload.get("senderNick", "")
        conversation_type = payload.get("conversationType", "1")
        conversation_id = payload.get("conversationId", "")
        session_webhook = payload.get("sessionWebhook", "")

        # Extract text content
        text_data = payload.get("text", {})
        content = (text_data.get("content", "") if isinstance(text_data, dict) else "").strip()

        # Strip @bot mention prefix
        content = _AT_BOT_PATTERN.sub("", content).strip()

        return IncomingMessage(
            user_id=user_id,
            tenant_id="",  # Resolved later via DB lookup
            content=content,
            session_id=conversation_id,
            channel=self.channel,
            meta={
                "sender_name": sender_name,
                "conversation_type": conversation_type,
                "conversation_id": conversation_id,
                "session_webhook": session_webhook,
            },
        )

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Send a text message via DingTalk session webhook.

        Args:
            to_handle: The sessionWebhook URL from the incoming message.
            text: Message text to send.
            meta: Optional metadata (unused for basic send).
        """
        if not to_handle:
            logger.warning("DingTalk send skipped: no session webhook URL")
            return

        body = {
            "msgtype": "text",
            "text": {"content": text},
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(to_handle, json=body)
            if resp.status_code != 200:
                logger.error(
                    "DingTalk send failed: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
            else:
                logger.info("DingTalk send success: %d chars", len(text))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_dingtalk_channel.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/channels/dingtalk.py tests/unit/test_dingtalk_channel.py
git commit -m "feat: add DingTalk channel with webhook send"
```

---

### Task 4: ChannelManager

**Files:**
- Create: `src/channels/manager.py`
- Test: `tests/unit/test_channel_manager.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/unit/test_channel_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.channels.manager'`

- [ ] **Step 3: Write minimal implementation**

Create `src/channels/manager.py`:

```python
"""ChannelManager: centralized outbound message routing."""

from __future__ import annotations

import logging
from typing import Any

from src.channels.base import BaseChannel

logger = logging.getLogger(__name__)


class ChannelManager:
    """Registry of channels with outbound send routing."""

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        """Register a channel instance."""
        self._channels[channel.channel] = channel
        logger.info("Registered channel: %s", channel.channel)

    def get(self, channel_type: str) -> BaseChannel | None:
        """Get a registered channel by type, or None."""
        return self._channels.get(channel_type)

    async def send(
        self,
        channel_type: str,
        to_handle: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Route an outbound message to the specified channel.

        Args:
            channel_type: Channel identifier (e.g., "dingtalk").
            to_handle: Routing handle for the channel.
            text: Message text.
            meta: Optional metadata.

        Raises:
            ValueError: If the channel type is not registered.
        """
        channel = self._channels.get(channel_type)
        if not channel:
            raise ValueError(f"Unknown channel: {channel_type}")
        await channel.send(to_handle, text, meta)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/unit/test_channel_manager.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/channels/manager.py tests/unit/test_channel_manager.py
git commit -m "feat: add ChannelManager for outbound routing"
```

---

### Task 5: Channel CRUD API

**Files:**
- Create: `src/api/channels.py`
- Modify: `src/custom_app.py:25-33` (register router)
- Test: `tests/integration/test_channel_api.py`

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for channel CRUD API."""

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_channel(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {"app_key": "test-key", "app_secret": "test-secret"},
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["channel_type"] == "dingtalk"
    assert data["config"]["app_key"] == "test-key"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_list_channels(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    # Create a channel first
    await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)

    resp = await async_client.get("/api/channels", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(c["channel_type"] == "dingtalk" for c in data)


@pytest.mark.asyncio
async def test_update_channel(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {"app_key": "old"},
    }, headers=headers)
    channel_id = resp.json()["id"]

    resp = await async_client.put(f"/api/channels/{channel_id}", json={
        "config": {"app_key": "new"},
        "enabled": False,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["config"]["app_key"] == "new"
    assert resp.json()["enabled"] is False


@pytest.mark.asyncio
async def test_delete_channel(async_client, tenant_with_user):
    headers = tenant_with_user["headers"]
    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)
    channel_id = resp.json()["id"]

    resp = await async_client.delete(f"/api/channels/{channel_id}", headers=headers)
    assert resp.status_code == 200

    # Verify deleted
    resp = await async_client.get("/api/channels", headers=headers)
    assert all(c["id"] != channel_id for c in resp.json())


@pytest.mark.asyncio
async def test_duplicate_channel_type_rejected(async_client, tenant_with_user):
    """UNIQUE(tenant_id, channel_type) constraint."""
    headers = tenant_with_user["headers"]
    await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)

    resp = await async_client.post("/api/channels", json={
        "channel_type": "dingtalk",
        "config": {},
    }, headers=headers)
    assert resp.status_code in (400, 409)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/integration/test_channel_api.py -v`
Expected: FAIL — route `/api/channels` not found (404)

- [ ] **Step 3: Write the API implementation**

Create `src/api/channels.py`:

```python
"""Channel configuration CRUD API."""

import json

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.channel import ChannelCreate, ChannelResponse, ChannelUpdate

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.get("", response_model=list[ChannelResponse])
async def list_channels(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM channels WHERE tenant_id = %s ORDER BY created_at",
        user["tenant_id"],
    )
    return [ChannelResponse(**r) for r in rows]


@router.post("", response_model=ChannelResponse, status_code=201)
async def create_channel(body: ChannelCreate, user: dict = Depends(get_current_user)):
    # Check for duplicate
    existing = await fetch_one(
        "SELECT id FROM channels WHERE tenant_id = %s AND channel_type = %s",
        user["tenant_id"],
        body.channel_type.value,
    )
    if existing:
        raise HTTPException(
            409,
            f"Channel '{body.channel_type.value}' already exists for this tenant",
        )

    row = await fetch_one(
        "INSERT INTO channels (tenant_id, channel_type, config, enabled) "
        "VALUES (%s, %s, %s, %s) RETURNING *",
        user["tenant_id"],
        body.channel_type.value,
        json.dumps(body.config),
        body.enabled,
    )
    return ChannelResponse(**row)


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    user: dict = Depends(get_current_user),
):
    existing = await fetch_one(
        "SELECT * FROM channels WHERE id = %s AND tenant_id = %s",
        channel_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Channel not found")

    updates = []
    params = []
    if body.config is not None:
        updates.append("config = %s")
        params.append(json.dumps(body.config))
    if body.enabled is not None:
        updates.append("enabled = %s")
        params.append(body.enabled)
    if body.agent_id is not None:
        updates.append("agent_id = %s")
        params.append(str(body.agent_id))

    if not updates:
        return ChannelResponse(**existing)

    params.append(channel_id)
    row = await fetch_one(
        f"UPDATE channels SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return ChannelResponse(**row)


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT id FROM channels WHERE id = %s AND tenant_id = %s",
        channel_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Channel not found")
    await execute("DELETE FROM channels WHERE id = %s", channel_id)
    return {"detail": "Deleted"}
```

- [ ] **Step 4: Register the router in custom_app.py**

Modify `src/custom_app.py` — add the import and `include_router`:

```python
from src.api.channels import router as channels_router
```

And after the existing `include_router` calls:

```python
app.include_router(channels_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/integration/test_channel_api.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/channels.py src/custom_app.py tests/integration/test_channel_api.py
git commit -m "feat: add channel CRUD API endpoints"
```

---

### Task 6: DingTalk Webhook Endpoint + Message Processing

**Files:**
- Modify: `src/channels/dingtalk.py` (add `process_message` method)
- Create: `src/api/webhooks.py` (DingTalk webhook receiver)
- Modify: `src/custom_app.py` (register webhook routes)
- Test: `tests/integration/test_dingtalk_webhook.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/integration/test_dingtalk_webhook.py -v`
Expected: FAIL — route `/webhooks/dingtalk` not found or module missing

- [ ] **Step 3: Write the webhook endpoint**

Create `src/api/webhooks.py`:

```python
"""Webhook endpoints for channel callbacks."""

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from src.channels.dingtalk import DingTalkChannel
from src.db.client import execute, fetch_one

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

_dingtalk_channel = DingTalkChannel()


async def _ensure_dingtalk_user(payload: dict[str, Any]) -> str:
    """Look up or create a DingTalk user, return tenant_id.

    Uses senderStaffId as user_id with channel_source='dingtalk'.
    If the user doesn't exist, returns empty string (message will be rejected).
    """
    user_id = payload.get("senderStaffId", "")
    if not user_id:
        return ""

    user = await fetch_one(
        "SELECT tenant_id::text, name FROM users "
        "WHERE id = %s AND channel_source = 'dingtalk'",
        user_id,
    )
    if user:
        return user["tenant_id"]

    return ""


async def _create_agent_run(
    tenant_id: str,
    user_id: str,
    content: str,
    session_id: str,
) -> str:
    """Create a LangGraph run and return the agent's response text.

    Uses the LangGraph SDK to create a wait-mode run.
    """
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")

    thread_id = f"{tenant_id}:{user_id}:dingtalk:{session_id}"

    # Ensure thread exists
    try:
        await client.threads.get(thread_id)
    except Exception:
        await client.threads.create(thread_id=thread_id)

    # Create run (wait mode — blocks until complete)
    result = await client.runs.wait(
        thread_id=thread_id,
        assistant_id="store-agent",
        input={
            "messages": [{"role": "user", "content": content}],
        },
        config={
            "configurable": {"tenant_id": tenant_id},
        },
        timeout=120,
    )

    # Extract last AI message from result
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if msg.get("type") == "ai" and msg.get("content"):
            return msg["content"]

    return "I'm sorry, I couldn't generate a response."


async def _send_dingtalk_reply(
    session_webhook: str, text: str
) -> None:
    """Send a reply via DingTalk session webhook."""
    await _dingtalk_channel.send(session_webhook, text)


async def _process_dingtalk_message(payload: dict[str, Any]) -> None:
    """Full pipeline: parse → lookup user → run agent → send reply."""
    msg = _dingtalk_channel.parse_incoming(payload)

    if not msg.user_id:
        logger.warning("DingTalk message with no senderStaffId, ignoring")
        return

    # Look up user's tenant
    tenant_id = await _ensure_dingtalk_user(payload)
    if not tenant_id:
        logger.warning(
            "DingTalk user %s not found in DB, ignoring", msg.user_id
        )
        session_webhook = msg.meta.get("session_webhook", "")
        if session_webhook:
            await _send_dingtalk_reply(
                session_webhook,
                "Sorry, your account is not configured. Please contact your administrator.",
            )
        return

    msg.tenant_id = tenant_id

    # Run agent
    try:
        response_text = await _create_agent_run(
            tenant_id=tenant_id,
            user_id=msg.user_id,
            content=msg.content,
            session_id=msg.session_id,
        )
    except Exception:
        logger.exception("Agent run failed for user %s", msg.user_id)
        response_text = "Sorry, an error occurred while processing your request."

    # Send reply
    session_webhook = msg.meta.get("session_webhook", "")
    if session_webhook:
        await _send_dingtalk_reply(session_webhook, response_text)
    else:
        logger.warning("No session webhook for user %s", msg.user_id)


@router.post("/webhooks/dingtalk")
async def dingtalk_webhook(request: Request):
    """Receive DingTalk robot callback messages.

    ACKs immediately (200), processes asynchronously.
    """
    payload = await request.json()

    # Basic validation
    sender = payload.get("senderStaffId")
    if not sender:
        raise HTTPException(400, "Missing senderStaffId")

    # Process asynchronously — don't block the ACK
    asyncio.create_task(_process_dingtalk_message(payload))

    return {"success": True}
```

- [ ] **Step 4: Register webhook routes in custom_app.py**

Modify `src/custom_app.py` — add the import and `include_router`:

```python
from src.api.webhooks import router as webhooks_router
```

And:

```python
app.include_router(webhooks_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/integration/test_dingtalk_webhook.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/webhooks.py src/custom_app.py tests/integration/test_dingtalk_webhook.py
git commit -m "feat: add DingTalk webhook endpoint with async message processing"
```

---

### Task 7: DingTalk User Auto-Provisioning

**Files:**
- Modify: `src/api/webhooks.py` (enhance `_ensure_dingtalk_user`)
- Modify: `src/api/webhooks.py` (add tenant lookup by channel config)
- Test: add to `tests/integration/test_dingtalk_webhook.py`

This task enhances the user lookup to auto-create DingTalk users under a tenant that has a DingTalk channel configured.

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_dingtalk_webhook.py`:

```python
@pytest.mark.asyncio
async def test_dingtalk_auto_provision_user(async_client, tenant_with_user, _init_pool):
    """New DingTalk user should be auto-created under the tenant with dingtalk channel."""
    from src.db.client import execute, fetch_one

    tenant_id = tenant_with_user["tenant_id"]

    # Create a dingtalk channel for this tenant
    await execute(
        "INSERT INTO channels (tenant_id, channel_type, config) "
        "VALUES (%s::uuid, 'dingtalk', '{}')",
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

    # Should find the tenant that has a dingtalk channel
    assert result_tenant == tenant_id

    # Verify user was created in DB
    user = await fetch_one(
        "SELECT id, tenant_id::text, name FROM users "
        "WHERE id = 'new-dt-user-999' AND channel_source = 'dingtalk'",
    )
    assert user is not None
    assert user["tenant_id"] == tenant_id
    assert user["name"] == "New DT User"

    # Cleanup
    await execute("DELETE FROM users WHERE id = 'new-dt-user-999'")
    await execute("DELETE FROM channels WHERE tenant_id = %s::uuid", tenant_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/integration/test_dingtalk_webhook.py::test_dingtalk_auto_provision_user -v`
Expected: FAIL — user not auto-created

- [ ] **Step 3: Enhance `_ensure_dingtalk_user`**

Replace the `_ensure_dingtalk_user` function in `src/api/webhooks.py` with:

```python
async def _ensure_dingtalk_user(payload: dict[str, Any]) -> str:
    """Look up or auto-create a DingTalk user.

    If the user exists, return their tenant_id.
    If not, find a tenant with a DingTalk channel configured and
    auto-create the user under that tenant.
    Returns empty string if no matching tenant found.
    """
    user_id = payload.get("senderStaffId", "")
    if not user_id:
        return ""

    # Check if user already exists
    user = await fetch_one(
        "SELECT tenant_id::text, name FROM users "
        "WHERE id = %s AND channel_source = 'dingtalk'",
        user_id,
    )
    if user:
        return user["tenant_id"]

    # Find a tenant with a dingtalk channel configured
    channel = await fetch_one(
        "SELECT c.tenant_id::text FROM channels c "
        "WHERE c.channel_type = 'dingtalk' AND c.enabled = true "
        "LIMIT 1",
    )
    if not channel:
        logger.warning("No tenant with dingtalk channel found for auto-provision")
        return ""

    tenant_id = channel["tenant_id"]
    sender_name = payload.get("senderNick", user_id)

    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) "
        "VALUES (%s, %s::uuid, %s, 'staff', 'dingtalk') "
        "ON CONFLICT (channel_source, id) DO NOTHING",
        user_id,
        tenant_id,
        sender_name,
    )
    logger.info(
        "Auto-provisioned DingTalk user %s under tenant %s",
        user_id,
        tenant_id,
    )
    return tenant_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/integration/test_dingtalk_webhook.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/webhooks.py tests/integration/test_dingtalk_webhook.py
git commit -m "feat: auto-provision DingTalk users under configured tenant"
```

---

### Task 8: Run Full Test Suite + Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `PYTHONUTF8=1 .venv/Scripts/python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (existing + new channel tests)

- [ ] **Step 2: Verify langgraph dev server starts**

```bash
export $(grep -v '^#' .env | xargs) PYTHONUTF8=1
PYTHONUTF8=1 .venv/Scripts/langgraph dev --no-browser
```

Verify:
- Server starts without errors
- Checkpointer connects to PostgreSQL
- Custom app loads with channel routes

- [ ] **Step 3: Test channel API via curl**

```bash
# Generate token
TOKEN=$(python -c "from src.auth import create_token; print(create_token('test-manager-001', 'a192eee7-9063-4ff7-b070-6db17e085076'))")

# Create channel
curl -X POST http://127.0.0.1:2024/api/channels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel_type": "dingtalk", "config": {"app_key": "test"}}'

# List channels
curl http://127.0.0.1:2024/api/channels \
  -H "Authorization: Bearer $TOKEN"
```

- [ ] **Step 4: Commit any remaining changes and push**

```bash
git push origin main
```
