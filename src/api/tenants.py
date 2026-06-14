"""Tenant management API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from starlette.requests import Request

from src.api.deps import get_current_user, get_tenant_id
from src.db.client import execute, fetch_all, fetch_one
from src.models.tenant import TenantCreate, TenantResponse

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def list_tenants(user: dict = Depends(get_current_user)):
    """List tenants accessible to the current user."""
    rows = await fetch_all(
        "SELECT id, name, config, created_at FROM tenants WHERE id = %s",
        user["tenant_id"],
    )
    return [TenantResponse(**row) for row in rows]


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(body: TenantCreate, user: dict = Depends(get_current_user)):
    """Create a new tenant."""
    row = await fetch_one(
        "INSERT INTO tenants (name, config) VALUES (%s, %s) "
        "RETURNING id, name, config, created_at",
        body.name,
        str(body.config) if body.config else "{}",
    )
    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (channel_source, id) DO NOTHING",
        user["sub"],
        str(row["id"]),
        "System",
        "manager",
        "console",
    )
    return TenantResponse(**row)
