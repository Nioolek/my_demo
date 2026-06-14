import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.unit


def test_get_builtin_tools_returns_list():
    from src.agent.tools import get_builtin_tools
    tools = get_builtin_tools()
    assert isinstance(tools, list)


@pytest.mark.asyncio
async def test_load_tenant_skills_empty():
    """When no skills exist, should return empty list."""
    from src.agent.tools import load_tenant_skills
    with patch("src.agent.tools.fetch_all", new_callable=AsyncMock, return_value=[]):
        tools = await load_tenant_skills("fake-tenant-id")
        assert tools == []
