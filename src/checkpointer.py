"""PostgresSaver factory for LangGraph Server."""

import os
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def create_checkpointer():
    """Create and yield an AsyncPostgresSaver.

    Referenced by langgraph.json checkpointer.path.
    LangGraph Server calls this once at startup.
    """
    uri = os.environ["DATABASE_URI"]
    async with AsyncPostgresSaver.from_conn_string(uri) as saver:
        await saver.setup()
        yield saver
