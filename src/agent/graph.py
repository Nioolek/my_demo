"""Dynamic agent graph factory for LangGraph Server.

Called on every Run with the current config. Builds a fresh
create_react_agent with the tenant's latest Skills/Tools/MCP.
"""

import os
from typing import Any

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agent.tools import get_builtin_tools, load_tenant_skills, load_mcp_tools
from src.db.client import fetch_one


def _get_default_model():
    """Get the default chat model. Uses ChatOpenAI as default."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=os.environ.get("DEFAULT_MODEL", "gpt-4o"),
        temperature=0.7,
    )


async def make_graph(config: dict, runtime: Any = None):
    """Build agent graph dynamically per-request.

    Referenced by langgraph.json graphs config.
    LangGraph Server calls this factory on every Run creation.

    Args:
        config: Run config with configurable containing tenant_id.
        runtime: LangGraph ServerRuntime with store access.
    """
    configurable = config.get("configurable", {})
    tenant_id = configurable.get("tenant_id")

    agent_config = None
    if tenant_id:
        agent_config = await fetch_one(
            "SELECT model, system_prompt, temperature, config FROM agents "
            "WHERE tenant_id = %s AND enabled = true LIMIT 1",
            tenant_id,
        )

    if agent_config:
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(
            model=agent_config["model"],
            temperature=agent_config["temperature"],
        )
        system_prompt = agent_config["system_prompt"]
    else:
        model = _get_default_model()
        system_prompt = "You are a helpful store manager assistant."

    tools = get_builtin_tools()
    if tenant_id:
        tools.extend(await load_tenant_skills(tenant_id))
        tools.extend(await load_mcp_tools(tenant_id))

    graph = create_react_agent(
        model=model,
        tools=tools if tools else None,
        prompt=system_prompt,
    )

    return graph
