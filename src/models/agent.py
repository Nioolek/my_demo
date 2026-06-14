"""Agent configuration data models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    tenant_id: UUID
    name: str = Field(default="default", max_length=255)
    model: str = Field(default="gpt-4o")
    system_prompt: str = Field(default="You are a helpful store manager assistant.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    config: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    model: str
    system_prompt: str
    temperature: float
    config: dict
    enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    config: dict | None = None
    enabled: bool | None = None
