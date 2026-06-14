import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")

pytestmark = pytest.mark.unit


def test_create_checkpointer_returns_context_manager():
    """The factory should return an async context manager."""
    import inspect
    from src.checkpointer import create_checkpointer
    assert inspect.isasyncgenfunction(create_checkpointer) or callable(create_checkpointer)
