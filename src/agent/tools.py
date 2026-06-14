"""Built-in tools and dynamic tool loading for the agent."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from src.db.client import fetch_all
from src.agent.skills import skill_to_tool
from src.models.skill import SkillResponse, SkillStatus, SkillScope


def get_builtin_tools() -> list[BaseTool]:
    """Return built-in tools available to all agents."""

    @tool
    def get_current_time() -> str:
        """Get the current date and time."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    return [get_current_time]


async def load_tenant_skills(tenant_id: str) -> list[BaseTool]:
    """Load all enabled, approved skills for a tenant and convert to tools."""
    system_rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE scope = %s AND status = %s",
        SkillScope.SYSTEM.value,
        SkillStatus.APPROVED.value,
    )

    tenant_rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE tenant_id = %s AND status = %s",
        tenant_id,
        SkillStatus.APPROVED.value,
    )

    tools = []
    for row in system_rows + tenant_rows:
        try:
            skill = SkillResponse(**row)
            tools.append(skill_to_tool(skill))
        except Exception:
            continue

    return tools


async def load_mcp_tools(tenant_id: str) -> list[BaseTool]:
    """Load MCP tools for a tenant."""
    from src.agent.mcp_loader import load_mcp_tools as _load
    return await _load(tenant_id)
