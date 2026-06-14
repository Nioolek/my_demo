import pytest

from src.db.client import fetch_all

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_tenants_table_exists(_init_pool):
    rows = await fetch_all(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'tenants'"
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_all_business_tables_exist(_init_pool):
    expected = {
        "tenants", "users", "agents", "skills_meta",
        "channels", "mcp_servers", "cron_jobs_meta", "threads_meta",
    }
    rows = await fetch_all(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = ANY(%s)",
        list(expected),
    )
    found = {r["table_name"] for r in rows}
    assert found == expected
