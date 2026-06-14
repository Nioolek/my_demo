"""MCP tool loader: connect to configured MCP servers and return LangChain tools."""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.db.client import fetch_all

logger = logging.getLogger(__name__)


async def load_mcp_tools(tenant_id: str) -> list[BaseTool]:
    """Load tools from all enabled MCP servers for a tenant.

    Connects to each server via langchain-mcp-adapters, collects all tools.
    System-level servers (tenant_id IS NULL) are included for all tenants.
    """
    rows = await fetch_all(
        "SELECT * FROM mcp_servers "
        "WHERE enabled = true AND (tenant_id = %s OR tenant_id IS NULL) "
        "ORDER BY created_at",
        tenant_id,
    )

    if not rows:
        return []

    # Build server configs for MultiServerMCPClient
    server_configs: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["name"]
        transport = row["transport"]
        config: dict[str, Any] = {"transport": transport}

        if transport == "stdio":
            config["command"] = row["command"]
            if row["args"]:
                config["args"] = row["args"]
            if row["env"]:
                config["env"] = row["env"]
        else:
            config["url"] = row["url"]

        server_configs[name] = config

    tools: list[BaseTool] = []
    try:
        async with MultiServerMCPClient(server_configs) as client:
            for name in server_configs.keys():
                raw_tools = await client.get_tools(server_name=name)
                for t in raw_tools:
                    # Prefix tool name with server name for disambiguation
                    t.name = f"mcp_{name}_{t.name}"
                    tools.append(t)
    except Exception:
        logger.exception("Failed to load MCP tools for tenant %s", tenant_id)

    logger.info("Loaded %d MCP tools for tenant %s", len(tools), tenant_id)
    return tools
