"""MCP server configuration CRUD API."""

import json

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.mcp import MCPServerCreate, MCPServerResponse, MCPServerUpdate

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("", response_model=list[MCPServerResponse])
async def list_mcp_servers(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM mcp_servers WHERE tenant_id = %s ORDER BY created_at",
        user["tenant_id"],
    )
    return [MCPServerResponse(**r) for r in rows]


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create_mcp_server(body: MCPServerCreate, user: dict = Depends(get_current_user)):
    row = await fetch_one(
        "INSERT INTO mcp_servers (tenant_id, name, transport, url, command, args, env, enabled) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        user["tenant_id"],
        body.name,
        body.transport.value,
        body.url,
        body.command,
        json.dumps(body.args),
        json.dumps(body.env),
        body.enabled,
    )
    return MCPServerResponse(**row)


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdate,
    user: dict = Depends(get_current_user),
):
    existing = await fetch_one(
        "SELECT * FROM mcp_servers WHERE id = %s AND tenant_id = %s",
        server_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "MCP server not found")

    updates = []
    params = []
    for field in ("name", "url", "command"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if body.transport is not None:
        updates.append("transport = %s")
        params.append(body.transport.value)
    if body.args is not None:
        updates.append("args = %s")
        params.append(json.dumps(body.args))
    if body.env is not None:
        updates.append("env = %s")
        params.append(json.dumps(body.env))
    if body.enabled is not None:
        updates.append("enabled = %s")
        params.append(body.enabled)

    if not updates:
        return MCPServerResponse(**existing)

    params.append(server_id)
    row = await fetch_one(
        f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return MCPServerResponse(**row)


@router.delete("/{server_id}")
async def delete_mcp_server(server_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT id FROM mcp_servers WHERE id = %s AND tenant_id = %s",
        server_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "MCP server not found")
    await execute("DELETE FROM mcp_servers WHERE id = %s", server_id)
    return {"detail": "Deleted"}