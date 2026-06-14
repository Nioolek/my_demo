"""Cron job CRUD API with LangGraph native cron sync."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.cron import CronJobCreate, CronJobResponse, CronJobUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cron-jobs", tags=["cron-jobs"])


async def _sync_to_langgraph(
    tenant_id: str,
    user_id: str,
    name: str,
    schedule: str,
    timezone: str,
    input_template: dict | None,
) -> str:
    """Create a LangGraph native cron job and return its cron_id."""
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")

    thread_id = f"{tenant_id}:{user_id}:cron:{name}"

    try:
        await client.threads.get(thread_id)
    except Exception:
        await client.threads.create(thread_id=thread_id)

    cron = await client.crons.create(
        assistant_id="store-agent",
        schedule=schedule,
        input=input_template or {"messages": [{"role": "user", "content": f"Cron job: {name}"}]},
        config={"configurable": {"tenant_id": tenant_id}},
        webhook="http://127.0.0.1:2024/webhooks/internal/cron-callback",
        timezone=timezone,
    )

    return cron["cron_id"]


async def _update_langgraph_cron(
    lg_cron_id: str,
    schedule: str | None = None,
    enabled: bool | None = None,
) -> None:
    """Update a LangGraph native cron job."""
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")

    kwargs = {}
    if schedule is not None:
        kwargs["schedule"] = schedule
    if enabled is not None:
        kwargs["enabled"] = enabled

    if kwargs:
        await client.crons.update(lg_cron_id, **kwargs)


async def _delete_from_langgraph(lg_cron_id: str) -> None:
    """Delete a LangGraph native cron job."""
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")
    await client.crons.delete(lg_cron_id)


@router.get("", response_model=list[CronJobResponse])
async def list_cron_jobs(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM cron_jobs_meta WHERE tenant_id = %s ORDER BY created_at DESC",
        user["tenant_id"],
    )
    return [CronJobResponse(**r) for r in rows]


@router.post("", response_model=CronJobResponse, status_code=201)
async def create_cron_job(body: CronJobCreate, user: dict = Depends(get_current_user)):
    try:
        lg_cron_id = await _sync_to_langgraph(
            tenant_id=user["tenant_id"],
            user_id=user["sub"],
            name=body.name,
            schedule=body.schedule,
            timezone=body.timezone,
            input_template=body.input_template,
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to create LangGraph cron: {e}")

    row = await fetch_one(
        "INSERT INTO cron_jobs_meta "
        "(tenant_id, agent_id, lg_cron_id, name, description, schedule, timezone, "
        " input_template, enabled, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        user["tenant_id"],
        str(body.agent_id) if body.agent_id else None,
        lg_cron_id,
        body.name,
        body.description,
        body.schedule,
        body.timezone,
        json.dumps(body.input_template) if body.input_template else None,
        body.enabled,
        user["sub"],
    )
    return CronJobResponse(**row)


@router.put("/{job_id}", response_model=CronJobResponse)
async def update_cron_job(
    job_id: str,
    body: CronJobUpdate,
    user: dict = Depends(get_current_user),
):
    existing = await fetch_one(
        "SELECT * FROM cron_jobs_meta WHERE id = %s AND tenant_id = %s",
        job_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Cron job not found")

    updates = []
    params = []
    for field in ("name", "description", "schedule", "timezone"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    if body.input_template is not None:
        updates.append("input_template = %s")
        params.append(json.dumps(body.input_template))
    if body.enabled is not None:
        updates.append("enabled = %s")
        params.append(body.enabled)
    if body.agent_id is not None:
        updates.append("agent_id = %s")
        params.append(str(body.agent_id))

    if not updates:
        return CronJobResponse(**existing)

    lg_cron_id = existing.get("lg_cron_id")
    if lg_cron_id and (body.schedule is not None or body.enabled is not None):
        try:
            await _update_langgraph_cron(
                lg_cron_id,
                schedule=body.schedule,
                enabled=body.enabled,
            )
        except Exception:
            logger.exception("Failed to update LangGraph cron %s", lg_cron_id)

    params.append(job_id)
    row = await fetch_one(
        f"UPDATE cron_jobs_meta SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return CronJobResponse(**row)


@router.delete("/{job_id}")
async def delete_cron_job(job_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT id, lg_cron_id FROM cron_jobs_meta WHERE id = %s AND tenant_id = %s",
        job_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Cron job not found")

    lg_cron_id = existing.get("lg_cron_id")
    if lg_cron_id:
        try:
            await _delete_from_langgraph(lg_cron_id)
        except Exception:
            logger.exception("Failed to delete LangGraph cron %s", lg_cron_id)

    await execute("DELETE FROM cron_jobs_meta WHERE id = %s", job_id)
    return {"detail": "Deleted"}


@router.post("/{job_id}/toggle", response_model=CronJobResponse)
async def toggle_cron_job(job_id: str, user: dict = Depends(get_current_user)):
    existing = await fetch_one(
        "SELECT * FROM cron_jobs_meta WHERE id = %s AND tenant_id = %s",
        job_id,
        user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Cron job not found")

    new_enabled = not existing["enabled"]

    lg_cron_id = existing.get("lg_cron_id")
    if lg_cron_id:
        try:
            await _update_langgraph_cron(lg_cron_id, enabled=new_enabled)
        except Exception:
            logger.exception("Failed to toggle LangGraph cron %s", lg_cron_id)

    row = await fetch_one(
        "UPDATE cron_jobs_meta SET enabled = %s WHERE id = %s RETURNING *",
        new_enabled,
        job_id,
    )
    return CronJobResponse(**row)