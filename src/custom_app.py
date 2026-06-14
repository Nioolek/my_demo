"""FastAPI custom app mounted into LangGraph Server via http.app config."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.db.client import get_pool, close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database pool lifecycle."""
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Store Agent Platform - Custom API",
    version="0.1.0",
    lifespan=lifespan,
)

from src.api.tenants import router as tenants_router
from src.api.auth_routes import router as auth_router
from src.api.skills import router as skills_router
from src.api.agents import router as agents_router
from src.api.channels import router as channels_router
from src.api.webhooks import router as webhooks_router
from src.api.mcp import router as mcp_router
from src.api.cron_jobs import router as cron_jobs_router

app.include_router(tenants_router)
app.include_router(auth_router)
app.include_router(skills_router)
app.include_router(agents_router)
app.include_router(channels_router)
app.include_router(webhooks_router)
app.include_router(mcp_router)
app.include_router(cron_jobs_router)
