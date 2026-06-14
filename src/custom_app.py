"""FastAPI custom app mounted into LangGraph Server via http.app config."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.db.client import get_pool, close_pool
from src.logging_config import setup_logging

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    enabled=os.environ.get("APP_ENV", "development") == "production",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database pool lifecycle."""
    setup_logging()
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Store Agent Platform - Custom API",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(429)
async def rate_limit_handler(request: Request, exc):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})

from src.api.tenants import router as tenants_router
from src.api.auth_routes import router as auth_router
from src.api.skills import router as skills_router
from src.api.agents import router as agents_router
from src.api.channels import router as channels_router
from src.api.webhooks import router as webhooks_router
from src.api.mcp import router as mcp_router
from src.api.cron_jobs import router as cron_jobs_router
from src.api.cron_callback import router as cron_callback_router

app.include_router(tenants_router)
app.include_router(auth_router)
app.include_router(skills_router)
app.include_router(agents_router)
app.include_router(channels_router)
app.include_router(webhooks_router)
app.include_router(mcp_router)
app.include_router(cron_jobs_router)
app.include_router(cron_callback_router)
