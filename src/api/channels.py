"""Channel configuration CRUD API."""

import json

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.channel import ChannelCreate, ChannelResponse, ChannelUpdate

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.get("", response_model=list[ChannelResponse])
async def list_channels(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM channels WHERE tenant_id = %s ORDER BY created_at",
        user["tenant_id"],
    )
    return [ChannelResponse(**r) for r in rows]


@router.post("", response_model=ChannelResponse, status_code=201)
async def create_channel(body: ChannelCreate, user: dict = Depends(get_current_user)):
    # Check for duplicate
    existing = await fetch_one(
        "SELECT id FROM channels WHERE tenant_id = %s AND channel_type = %s",
        user["tenant_id"],
        body.channel_type.value,
    )
    if existing:
        raise HTTPException(
            409,
            f"Channel '{body.channel_type.value}' already exists for this tenant",
        )

    row = await fetch_one(
        "INSERT INTO channels (tenant_id, channel_type, config, enabled) "
        "VALUES (%s, %s, %s, %s) RETURNING *",
        user["tenant_id"],
        body.channel_type.value,
        json.dumps(body.config),
        body.enabled,
    )
    return ChannelResponse(**row)


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    user: dict = Depends(get_current_user),
):
    existing = await fetch_one(
        "SELECT * FROM channels WHERE id = %s AND tenant_id = %s",
        channel_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Channel not found")

    updates = []
    params = []
    if body.config is not None:
        updates.append("config = %s")
        params.append(json.dumps(body.config))
    if body.enabled is not None:
        updates.append("enabled = %s")
        params.append(body.enabled)
    if body.agent_id is not None:
        updates.append("agent_id = %s")
        params.append(str(body.agent_id))

    if not updates:
        return ChannelResponse(**existing)

    params.append(channel_id)
    row = await fetch_one(
        f"UPDATE channels SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return ChannelResponse(**row)


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT id FROM channels WHERE id = %s AND tenant_id = %s",
        channel_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Channel not found")
    await execute("DELETE FROM channels WHERE id = %s", channel_id)
    return {"detail": "Deleted"}
