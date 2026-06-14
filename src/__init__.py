"""Store Agent Platform."""

import asyncio
import sys

# psycopg3 async pool requires SelectorEventLoop on Windows.
# Must be set before any event loop is created.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
