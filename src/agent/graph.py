"""Dynamic agent graph factory for LangGraph Server.

Called on every Run with the current config. Builds a fresh
create_react_agent with the tenant's latest Skills/Tools/MCP.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from langgraph_sdk.runtime import ServerRuntime

from src.agent.tools import get_builtin_tools, load_tenant_skills, load_mcp_tools
from src.db.client import fetch_one

log = logging.getLogger(__name__)

# Ensure .env is loaded (project root)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)


def _get_default_model():
    """Get the default chat model. Uses ChatOpenAI as default."""
    from langchain_openai import ChatOpenAI
    model_name = os.environ.get("OPENAI_API_MODEL", "gpt-4o")
    log.info("Using model: %s, base_url: %s", model_name, os.environ.get("OPENAI_BASE_URL"))
    return ChatOpenAI(
        model=model_name,
        temperature=0.7,
    )


async def make_graph(config: RunnableConfig, runtime: ServerRuntime):
    """Build agent graph dynamically per-request.

    Referenced by langgraph.json graphs config.
    LangGraph Server calls this factory on every Run creation.

    Args:
        config: Run config with configurable containing tenant_id.
        runtime: LangGraph ServerRuntime with store access.
    """
    configurable = config.get("configurable", {})
    tenant_id = configurable.get("tenant_id")
    log.info("make_graph called: tenant_id=%s", tenant_id)

    agent_config = None
    if tenant_id:
        try:
            agent_config = await fetch_one(
                "SELECT model, system_prompt, temperature, config FROM agents "
                "WHERE tenant_id = %s AND enabled = true LIMIT 1",
                tenant_id,
            )
        except Exception:
            log.exception("Failed to load agent config for tenant %s", tenant_id)

    if agent_config:
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(
            model=agent_config["model"],
            temperature=agent_config["temperature"],
        )
        system_prompt = agent_config["system_prompt"]
        log.info("Loaded tenant agent config: model=%s", agent_config["model"])
    else:
        model = _get_default_model()
        system_prompt = "You are a helpful store manager assistant."

    tools = get_builtin_tools()
    if tenant_id:
        try:
            skills = await load_tenant_skills(tenant_id)
            tools.extend(skills)
            log.info("Loaded %d skills for tenant %s", len(skills), tenant_id)
        except Exception:
            log.exception("Failed to load skills for tenant %s", tenant_id)

        try:
            mcp = await load_mcp_tools(tenant_id)
            tools.extend(mcp)
            log.info("Loaded %d MCP tools for tenant %s", len(mcp), tenant_id)
        except Exception:
            log.exception("Failed to load MCP tools for tenant %s", tenant_id)

    graph = create_react_agent(
        model=model,
        tools=tools if tools else None,
        prompt=system_prompt,
    )
    log.info("Graph built with %d tools", len(tools))

    return graph
