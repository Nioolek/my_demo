"""Tenant and user data models."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    config: dict = Field(default_factory=dict)


class TenantResponse(BaseModel):
    id: UUID
    name: str
    config: dict = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    id: str = Field(..., max_length=128)
    tenant_id: UUID
    name: str = Field(..., max_length=255)
    role: str = Field(default="staff", pattern="^(manager|staff|admin)$")
    channel_source: str = Field(default="console")


class UserResponse(BaseModel):
    id: str
    tenant_id: UUID
    name: str
    role: str
    channel_source: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
