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
