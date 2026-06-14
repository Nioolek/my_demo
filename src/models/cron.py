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
