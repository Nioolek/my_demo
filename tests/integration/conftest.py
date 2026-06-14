"""Shared fixtures for integration tests."""

import os
import uuid
from contextlib import asynccontextmanager

import pytest
import httpx

from src.auth import create_token
from src.db.client import execute, close_pool, get_pool

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")


@pytest.fixture(scope="session")
async def _init_pool():
    """Initialize the DB pool once for the entire test session."""
    await get_pool()
    yield
    await close_pool()


@pytest.fixture
async def async_client(_init_pool):
    """Async HTTP client for testing FastAPI endpoints."""
    from src.custom_app import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def tenant_with_user(_init_pool):
    """Create a tenant with a manager user, yield tokens, then cleanup."""
    tenant_id = str(uuid.uuid4())
    user_id = f"tenant-user-{uuid.uuid4().hex[:8]}"

    await execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", tenant_id, "Test Tenant")
    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES (%s,%s,%s,%s,%s)",
        user_id, tenant_id, "Manager", "manager", "console",
    )

    token = create_token(user_id, tenant_id)
    yield {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "headers": {"authorization": f"Bearer {token}"},
    }

    await execute("DELETE FROM users WHERE tenant_id = %s", tenant_id)
    await execute("DELETE FROM tenants WHERE id = %s", tenant_id)


@pytest.fixture
async def tenant_with_admin(_init_pool):
    """Create a tenant with both manager and admin users."""
    tenant_id = str(uuid.uuid4())
    mgr_id = f"mgr-{uuid.uuid4().hex[:8]}"
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"

    await execute("INSERT INTO tenants (id, name) VALUES (%s, %s)", tenant_id, "Admin Test")
    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES (%s,%s,%s,%s,%s)",
        mgr_id, tenant_id, "Manager", "manager", "console",
    )
    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES (%s,%s,%s,%s,%s)",
        admin_id, tenant_id, "Admin", "admin", "console",
    )

    mgr_token = create_token(mgr_id, tenant_id)
    admin_token = create_token(admin_id, tenant_id)

    yield {
        "tenant_id": tenant_id,
        "mgr_headers": {"authorization": f"Bearer {mgr_token}"},
        "admin_headers": {"authorization": f"Bearer {admin_token}"},
    }

    await execute("DELETE FROM skills_meta WHERE tenant_id = %s", tenant_id)
    await execute("DELETE FROM agents WHERE tenant_id = %s", tenant_id)
    await execute("DELETE FROM users WHERE tenant_id = %s", tenant_id)
    await execute("DELETE FROM tenants WHERE id = %s", tenant_id)
