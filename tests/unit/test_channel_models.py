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
