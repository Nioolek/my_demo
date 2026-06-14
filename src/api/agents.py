"""Agent configuration API routes."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.agent import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentResponse])
async def list_agents(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM agents WHERE tenant_id = %s ORDER BY created_at",
        user["tenant_id"],
    )
    return [AgentResponse(**r) for r in rows]


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(body: AgentCreate, user: dict = Depends(get_current_user)):
    body.tenant_id = __import__("uuid").UUID(user["tenant_id"])
    row = await fetch_one(
        "INSERT INTO agents (tenant_id, name, model, system_prompt, temperature, config) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
        user["tenant_id"], body.name, body.model, body.system_prompt,
        body.temperature, str(body.config),
    )
    return AgentResponse(**row)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, user: dict = Depends(get_current_user)):
    row = await fetch_one(
        "SELECT * FROM agents WHERE id = %s AND tenant_id = %s",
        agent_id, user["tenant_id"],
    )
    if not row:
        raise HTTPException(404, "Agent not found")
    return AgentResponse(**row)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str, body: AgentUpdate, user: dict = Depends(get_current_user)
):
    existing = await fetch_one(
        "SELECT * FROM agents WHERE id = %s AND tenant_id = %s",
        agent_id, user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Agent not found")

    updates = []
    params = []
    for field in ("name", "model", "system_prompt", "temperature", "config", "enabled"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(str(val) if isinstance(val, dict) else val)

    if not updates:
        return AgentResponse(**existing)

    params.append(agent_id)
    row = await fetch_one(
        f"UPDATE agents SET {', '.join(updates)} WHERE id = %s RETURNING *",
        *params,
    )
    return AgentResponse(**row)
