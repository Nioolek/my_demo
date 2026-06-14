"""Skill metadata and workflow models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class SkillStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISABLED = "disabled"


class SkillScope(str, Enum):
    SYSTEM = "system"
    TENANT = "tenant"
    USER = "user"


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9_-]+$")
    scope: SkillScope = Field(default=SkillScope.TENANT)
    status: SkillStatus = Field(default=SkillStatus.DRAFT)
    content: str = Field(..., min_length=1)
    config: dict = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["all"])


class SkillResponse(BaseModel):
    id: UUID
    tenant_id: UUID | None = None
    name: str
    scope: SkillScope
    status: SkillStatus
    content: str
    created_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    config: dict
    channels: list[str]
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SkillUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    config: dict | None = None
    channels: list[str] | None = None


class SkillApprovalRequest(BaseModel):
    approved: bool
    rejection_reason: str | None = None
