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
