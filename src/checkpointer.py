"""PostgresSaver factory for LangGraph Server."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# langgraph dev sets DATABASE_URI=:memory: by default.
# Override with our .env to use PostgreSQL.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


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
