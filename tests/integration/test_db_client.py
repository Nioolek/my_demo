import pytest

from src.db.client import get_pool, execute, fetch_one, fetch_all

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_pool_connects(_init_pool):
    pool = await get_pool()
    assert pool is not None
    result = await fetch_one("SELECT 1 AS val")
    assert result["val"] == 1


@pytest.mark.asyncio
async def test_execute_insert_and_fetch(_init_pool):
    await execute("CREATE TABLE IF NOT EXISTS _test_tbl (id INT, name TEXT)")
    await execute("INSERT INTO _test_tbl (id, name) VALUES (%s, %s)", 1, "alice")
    row = await fetch_one("SELECT name FROM _test_tbl WHERE id = %s", 1)
    assert row["name"] == "alice"
    await execute("DROP TABLE _test_tbl")


@pytest.mark.asyncio
async def test_fetch_all(_init_pool):
    await execute("CREATE TABLE IF NOT EXISTS _test_tbl2 (id INT)")
    await execute("INSERT INTO _test_tbl2 VALUES (%s)", 1)
    await execute("INSERT INTO _test_tbl2 VALUES (%s)", 2)
    rows = await fetch_all("SELECT id FROM _test_tbl2 ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["id"] == 1
    assert rows[1]["id"] == 2
    await execute("DROP TABLE _test_tbl2")
