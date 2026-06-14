"""Skill management API with approval workflow."""

import json

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.skill import (
    SkillCreate, SkillResponse, SkillUpdate,
    SkillStatus, SkillScope, SkillApprovalRequest,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillResponse])
async def list_skills(user: dict = Depends(get_current_user)):
    """List all skills for the current tenant."""
    rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE tenant_id = %s OR scope = 'system' "
        "ORDER BY created_at DESC",
        user["tenant_id"],
    )
    return [SkillResponse(**r) for r in rows]


@router.post("", response_model=SkillResponse, status_code=201)
async def create_skill(body: SkillCreate, user: dict = Depends(get_current_user)):
    """Create a new skill (status=draft)."""
    row = await fetch_one(
        "INSERT INTO skills_meta (tenant_id, name, scope, status, content, created_by, config, channels) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "RETURNING *",
        user["tenant_id"],
        body.name,
        body.scope.value,
        SkillStatus.DRAFT.value,
        body.content,
        user["sub"],
        json.dumps(body.config),
        json.dumps(body.channels),
    )
    return SkillResponse(**row)


@router.get("/pending", response_model=list[SkillResponse])
async def list_pending_skills(user: dict = Depends(get_current_user)):
    """List all pending skills (admin view)."""
    rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE status = %s ORDER BY updated_at DESC",
        SkillStatus.PENDING.value,
    )
    return [SkillResponse(**r) for r in rows]


@router.get("/system", response_model=list[SkillResponse])
async def list_system_skills(user: dict = Depends(get_current_user)):
    """List system-level skills (read-only)."""
    rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE scope = %s ORDER BY name",
        SkillScope.SYSTEM.value,
    )
    return [SkillResponse(**r) for r in rows]


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str, body: SkillUpdate, user: dict = Depends(get_current_user)
):
    """Update a skill (only draft or rejected skills can be edited)."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = %s", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] not in (SkillStatus.DRAFT.value, SkillStatus.REJECTED.value):
        raise HTTPException(400, "Only draft or rejected skills can be edited")

    updates = []
    params = []
    idx = 1
    if body.name is not None:
        updates.append(f"name = %s")
        params.append(body.name)
    if body.content is not None:
        updates.append(f"content = %s")
        params.append(body.content)
    if body.config is not None:
        updates.append(f"config = %s")
        params.append(json.dumps(body.config))

    if not updates:
        return SkillResponse(**skill)

    updates.append("updated_at = NOW()")
    params.append(skill_id)

    row = await fetch_one(
        f"UPDATE skills_meta SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/submit", response_model=SkillResponse)
async def submit_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Submit a draft skill for approval."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = %s", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] not in (SkillStatus.DRAFT.value, SkillStatus.REJECTED.value):
        raise HTTPException(400, "Only draft or rejected skills can be submitted")

    row = await fetch_one(
        "UPDATE skills_meta SET status = %s, updated_at = NOW() WHERE id = %s RETURNING *",
        SkillStatus.PENDING.value,
        skill_id,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/approve", response_model=SkillResponse)
async def approve_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Approve a pending skill (admin only)."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = %s", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] != SkillStatus.PENDING.value:
        raise HTTPException(400, "Only pending skills can be approved")

    row = await fetch_one(
        "UPDATE skills_meta SET status = %s, approved_by = %s, approved_at = NOW(), "
        "updated_at = NOW() WHERE id = %s RETURNING *",
        SkillStatus.APPROVED.value,
        user["sub"],
        skill_id,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/reject", response_model=SkillResponse)
async def reject_skill(
    skill_id: str,
    body: SkillApprovalRequest,
    user: dict = Depends(get_current_user),
):
    """Reject a pending skill (admin only)."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = %s", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] != SkillStatus.PENDING.value:
        raise HTTPException(400, "Only pending skills can be rejected")

    row = await fetch_one(
        "UPDATE skills_meta SET status = %s, approved_by = %s, "
        "rejection_reason = %s, updated_at = NOW() WHERE id = %s RETURNING *",
        SkillStatus.REJECTED.value,
        user["sub"],
        body.rejection_reason,
        skill_id,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/enable", response_model=SkillResponse)
async def enable_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Enable an approved skill."""
    row = await fetch_one(
        "UPDATE skills_meta SET status = %s, updated_at = NOW() WHERE id = %s RETURNING *",
        SkillStatus.APPROVED.value,
        skill_id,
    )
    if not row:
        raise HTTPException(404, "Skill not found")
    return SkillResponse(**row)


@router.post("/{skill_id}/disable", response_model=SkillResponse)
async def disable_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Disable a skill."""
    row = await fetch_one(
        "UPDATE skills_meta SET status = %s, updated_at = NOW() WHERE id = %s RETURNING *",
        SkillStatus.DISABLED.value,
        skill_id,
    )
    if not row:
        raise HTTPException(404, "Skill not found")
    return SkillResponse(**row)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Delete a disabled skill."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = %s", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] != SkillStatus.DISABLED.value:
        raise HTTPException(400, "Only disabled skills can be deleted")
    await execute("DELETE FROM skills_meta WHERE id = %s", skill_id)
    return {"detail": "Deleted"}
