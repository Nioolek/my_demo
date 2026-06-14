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
