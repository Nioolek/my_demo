# Phase 1: Foundation + Core Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the multi-tenant agent platform foundation with PostgreSQL, auth, dynamic agent graph, skill system with approval workflow, and a working console chat UI.

**Architecture:** LangGraph Server (`langgraph-api` pip package) with a custom FastAPI app mounted via `http.app`. Agent graph is built dynamically per-request via `make_graph(config, runtime)` factory. PostgreSQL stores both LangGraph native data (checkpoints, store) and business data (tenants, users, skills, agents). Auth uses LangGraph's `auth.path` for JWT verification and resource-level tenant filtering.

**Tech Stack:** Python 3.13, langgraph-api 0.10+, langgraph-prebuilt, langgraph-checkpoint-postgres, FastAPI, Pydantic v2, psycopg3, PyJWT, Docker (PostgreSQL), React 18 + Ant Design + TypeScript (forked QwenPaw Console).

**Reference:** Design spec at `docs/superpowers/specs/2026-06-14-multi-tenant-store-agent-design.md`. QwenPaw reference code at `CoPaw_fork/`.

---

## File Structure

```
project-root/
├── langgraph.json                  # LangGraph Server config
├── pyproject.toml                  # Python package config
├── .env                            # Environment variables
├── docker-compose.yml              # PostgreSQL container
├── Makefile                        # Common commands
├── src/
│   ├── __init__.py
│   ├── auth.py                     # Multi-tenant auth (authenticate + authorize)
│   ├── checkpointer.py            # PostgresSaver factory
│   ├── custom_app.py              # FastAPI app (http.app entry point)
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py               # make_graph() factory
│   │   ├── skills.py              # Skill → Tool conversion
│   │   └── tools.py               # Built-in tools
│   ├── db/
│   │   ├── __init__.py
│   │   ├── client.py              # Async PG connection pool
│   │   └── migrations/
│   │       ├── __init__.py
│   │       ├── runner.py          # Migration runner
│   │       └── 001_initial.sql    # Initial schema
│   ├── models/
│   │   ├── __init__.py
│   │   ├── tenant.py              # Tenant, User models
│   │   ├── agent.py               # Agent config model
│   │   └── skill.py               # Skill metadata + status enum
│   └── api/
│       ├── __init__.py
│       ├── deps.py                # FastAPI dependencies (get_current_user, get_tenant)
│       ├── tenants.py             # Tenant CRUD routes
│       ├── agents.py              # Agent config routes
│       ├── skills.py              # Skill CRUD + approval routes
│       └── auth_routes.py         # Login/token routes
├── console/                       # Forked QwenPaw Console (Phase 1: minimal)
│   └── ... (frontend files)
└── tests/
    ├── conftest.py                # Shared fixtures (test DB, test client)
    ├── unit/
    │   ├── test_models.py
    │   ├── test_auth.py
    │   ├── test_skill_parser.py
    │   └── test_graph_factory.py
    ├── integration/
    │   ├── test_db_client.py
    │   ├── test_migrations.py
    │   ├── test_tenant_api.py
    │   ├── test_skill_api.py
    │   └── test_auth_api.py
    └── e2e/
        └── test_chat_flow.py
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `langgraph.json`
- Create: `.env`
- Create: `docker-compose.yml`
- Create: `Makefile`
- Create: `.gitignore`
- Create: all `__init__.py` files in src/

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "store-agent-platform"
version = "0.1.0"
description = "Multi-tenant AI agent platform for retail store managers"
requires-python = ">=3.13"
dependencies = [
    "langgraph-api>=0.10.0",
    "langgraph-prebuilt>=1.1.0",
    "langgraph-checkpoint-postgres>=2.0.0",
    "langgraph-sdk>=0.4.0",
    "langchain-core>=1.4.0",
    "langchain-openai>=0.3.0",
    "fastapi>=0.115.0",
    "pydantic>=2.13.0",
    "psycopg[binary,pool]>=3.2.0",
    "PyJWT>=2.9.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.28.0",
    "uvicorn>=0.34.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.35.0",
    "httpx>=0.28.0",
    "testcontainers[postgres]>=4.9.0",
]

[build-system]
requires = ["setuptools>=82.0"]
build-backend = "setuptools.backends.legacy:build"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "unit: unit tests",
    "integration: integration tests requiring DB",
    "e2e: end-to-end tests",
]
```

- [ ] **Step 2: Write langgraph.json**

```json
{
  "dependencies": ["."],
  "graphs": {
    "store-agent": "./src/agent/graph.py:make_graph"
  },
  "env": ".env",
  "http": {
    "app": "./src/custom_app.py:app",
    "enable_custom_route_auth": true,
    "middleware_order": "auth_first"
  },
  "auth": {
    "path": "./src/auth.py:auth"
  },
  "checkpointer": {
    "path": "./src/checkpointer.py:create_checkpointer"
  }
}
```

- [ ] **Step 3: Write .env**

```
DATABASE_URI=postgresql://storeagent:storeagent@localhost:5432/storeagent
JWT_SECRET=dev-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

- [ ] **Step 4: Write docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: storeagent
      POSTGRES_PASSWORD: storeagent
      POSTGRES_DB: storeagent
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U storeagent"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

- [ ] **Step 5: Write Makefile**

```makefile
.PHONY: setup db-up db-down test test-unit test-integration lint dev

setup:
	.venv/Scripts/pip install -e ".[dev]"

db-up:
	docker compose up -d postgres
	@echo "Waiting for PostgreSQL..."
	@timeout 30 bash -c 'until docker compose exec -T postgres pg_isready -U storeagent 2>/dev/null; do sleep 1; done'
	@echo "PostgreSQL is ready."

db-down:
	docker compose down

migrate:
	.venv/Scripts/python -m src.db.migrations.runner

test-unit:
	.venv/Scripts/pytest tests/unit/ -v

test-integration:
	.venv/Scripts/pytest tests/integration/ -v

test:
	.venv/Scripts/pytest tests/ -v

dev:
	.venv/Scripts/langgraph dev --no-browser
```

- [ ] **Step 6: Write .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
.venv/
.env
*.egg
.pytest_cache/
.mypy_cache/
dist/
build/
node_modules/
console/dist/
console/node_modules/
```

- [ ] **Step 7: Create directory structure with __init__.py files**

```bash
mkdir -p src/agent src/db/migrations src/models src/api tests/unit tests/integration tests/e2e
touch src/__init__.py src/agent/__init__.py src/db/__init__.py src/db/migrations/__init__.py
touch src/models/__init__.py src/api/__init__.py
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/e2e/__init__.py
```

- [ ] **Step 8: Install dependencies**

```bash
cd G:/code/my_demo && source .venv/Scripts/activate && pip install -e ".[dev]"
```

- [ ] **Step 9: Verify installation**

```bash
python -c "import langgraph_api; import langgraph_prebuilt; import fastapi; import psycopg; import jwt; print('All imports OK')"
```

Expected: `All imports OK`

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml langgraph.json .env docker-compose.yml Makefile .gitignore src/ tests/
git commit -m "chore: project scaffolding with langgraph.json, deps, docker-compose"
```

---

## Task 2: Database Client & Migration Runner

**Files:**
- Create: `src/db/client.py`
- Create: `src/db/migrations/runner.py`
- Create: `src/db/migrations/001_initial.sql`
- Create: `tests/integration/test_db_client.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Start PostgreSQL**

```bash
make db-up
```

Expected: PostgreSQL container running and healthy.

- [ ] **Step 2: Write the failing test for DB client**

```python
# tests/conftest.py
import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")


# tests/integration/test_db_client.py
import pytest
from src.db.client import get_pool, execute, fetch_one, fetch_all

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_pool_connects():
    pool = await get_pool()
    assert pool is not None
    result = await fetch_one("SELECT 1 AS val")
    assert result["val"] == 1


@pytest.mark.asyncio
async def test_execute_insert_and_fetch():
    await execute("CREATE TABLE IF NOT EXISTS _test_tbl (id INT, name TEXT)")
    await execute("INSERT INTO _test_tbl (id, name) VALUES ($1, $2)", 1, "alice")
    row = await fetch_one("SELECT name FROM _test_tbl WHERE id = $1", 1)
    assert row["name"] == "alice"
    await execute("DROP TABLE _test_tbl")


@pytest.mark.asyncio
async def test_fetch_all():
    await execute("CREATE TABLE IF NOT EXISTS _test_tbl2 (id INT)")
    await execute("INSERT INTO _test_tbl2 VALUES ($1)", 1)
    await execute("INSERT INTO _test_tbl2 VALUES ($1)", 2)
    rows = await fetch_all("SELECT id FROM _test_tbl2 ORDER BY id")
    assert len(rows) == 2
    assert rows[0]["id"] == 1
    assert rows[1]["id"] == 2
    await execute("DROP TABLE _test_tbl2")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/integration/test_db_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.client'`

- [ ] **Step 4: Implement DB client**

```python
# src/db/client.py
"""Async PostgreSQL connection pool and query helpers."""

import os
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    """Get or create the global async connection pool."""
    global _pool
    if _pool is None:
        uri = os.environ["DATABASE_URI"]
        _pool = AsyncConnectionPool(
            conninfo=uri,
            min_size=2,
            max_size=20,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )
        await _pool.open()
    return _pool


async def close_pool() -> None:
    """Close the global pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def execute(query: str, *args: Any) -> None:
    """Execute a query without returning results."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(query, args)


async def fetch_one(query: str, *args: Any) -> dict[str, Any] | None:
    """Execute a query and return a single row."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(query, args)
        return await cursor.fetchone()


async def fetch_all(query: str, *args: Any) -> list[dict[str, Any]]:
    """Execute a query and return all rows."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cursor = await conn.execute(query, args)
        return await cursor.fetchall()


@asynccontextmanager
async def transaction():
    """Context manager for a database transaction."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute("BEGIN")
        try:
            yield conn
            await conn.execute("COMMIT")
        except Exception:
            await conn.execute("ROLLBACK")
            raise
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/integration/test_db_client.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Write migration SQL**

```sql
-- src/db/migrations/001_initial.sql

-- Tenants (stores)
CREATE TABLE IF NOT EXISTS tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    config          JSONB NOT NULL DEFAULT '{}'
);

-- Users (store managers/staff)
CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR(128) NOT NULL,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'staff',
    channel_source  VARCHAR(50) NOT NULL DEFAULT 'console',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (channel_source, id)
);

CREATE INDEX idx_users_tenant ON users(tenant_id);

-- Agent configuration (one per tenant)
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL DEFAULT 'default',
    model           VARCHAR(255) NOT NULL DEFAULT 'gpt-4o',
    system_prompt   TEXT NOT NULL DEFAULT 'You are a helpful store manager assistant.',
    temperature     FLOAT NOT NULL DEFAULT 0.7,
    config          JSONB NOT NULL DEFAULT '{}',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Skill metadata with approval workflow
CREATE TABLE IF NOT EXISTS skills_meta (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    scope           VARCHAR(50) NOT NULL DEFAULT 'tenant',
    status          VARCHAR(50) NOT NULL DEFAULT 'draft',
    content         TEXT NOT NULL DEFAULT '',
    created_by      VARCHAR(128),
    approved_by     VARCHAR(128),
    approved_at     TIMESTAMPTZ,
    rejection_reason TEXT,
    config          JSONB NOT NULL DEFAULT '{}',
    channels        JSONB NOT NULL DEFAULT '["all"]',
    version         INT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_skills_tenant ON skills_meta(tenant_id);
CREATE INDEX idx_skills_status ON skills_meta(status);
CREATE INDEX idx_skills_scope ON skills_meta(scope);

-- Channel configuration
CREATE TABLE IF NOT EXISTS channels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id        UUID REFERENCES agents(id) ON DELETE SET NULL,
    channel_type    VARCHAR(50) NOT NULL,
    config          JSONB NOT NULL DEFAULT '{}',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, channel_type)
);

-- MCP server configuration
CREATE TABLE IF NOT EXISTS mcp_servers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    transport       VARCHAR(50) NOT NULL DEFAULT 'sse',
    url             TEXT,
    command         TEXT,
    args            JSONB NOT NULL DEFAULT '[]',
    env             JSONB NOT NULL DEFAULT '{}',
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cron job metadata (extends LangGraph native cron)
CREATE TABLE IF NOT EXISTS cron_jobs_meta (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id        UUID REFERENCES agents(id) ON DELETE SET NULL,
    lg_cron_id      VARCHAR(255),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    schedule        VARCHAR(255) NOT NULL,
    timezone        VARCHAR(100) NOT NULL DEFAULT 'Asia/Shanghai',
    input_template  JSONB,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Thread metadata (extends LangGraph native threads)
CREATE TABLE IF NOT EXISTS threads_meta (
    thread_id       VARCHAR(255) PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id        UUID REFERENCES agents(id) ON DELETE SET NULL,
    user_id         VARCHAR(128),
    channel_type    VARCHAR(50) NOT NULL DEFAULT 'console',
    title           VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_threads_tenant ON threads_meta(tenant_id);
CREATE INDEX idx_threads_user ON threads_meta(user_id);
```

- [ ] **Step 7: Implement migration runner**

```python
# src/db/migrations/runner.py
"""Run SQL migration files against the database."""

import os
import glob
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent


def run_migrations():
    """Execute all .sql migration files in order."""
    uri = os.environ.get("DATABASE_URI")
    if not uri:
        raise RuntimeError("DATABASE_URI not set")

    sql_files = sorted(glob.glob(str(MIGRATIONS_DIR / "*.sql")))
    if not sql_files:
        print("No migration files found.")
        return

    with psycopg.connect(uri, autocommit=True) as conn:
        # Create tracking table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        for sql_file in sql_files:
            filename = os.path.basename(sql_file)
            cursor = conn.execute(
                "SELECT 1 FROM _migrations WHERE filename = %s", (filename,)
            )
            if cursor.fetchone():
                print(f"  SKIP {filename} (already applied)")
                continue

            print(f"  APPLY {filename}...")
            with open(sql_file, "r") as f:
                sql = f.read()
            conn.execute(sql)
            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (%s)", (filename,)
            )
            print(f"  DONE {filename}")

    print("All migrations complete.")


if __name__ == "__main__":
    run_migrations()
```

- [ ] **Step 8: Run migrations**

```bash
make migrate
```

Expected: All migration files applied successfully.

- [ ] **Step 9: Write migration test**

```python
# tests/integration/test_migrations.py
import pytest
from src.db.client import fetch_all, execute

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_tenants_table_exists():
    rows = await fetch_all(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'tenants'"
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_all_business_tables_exist():
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
```

- [ ] **Step 10: Run all integration tests**

```bash
python -m pytest tests/integration/ -v
```

Expected: All PASSED

- [ ] **Step 11: Commit**

```bash
git add src/db/ tests/conftest.py tests/integration/test_db_client.py tests/integration/test_migrations.py
git commit -m "feat: add async PG client, migration runner, initial schema"
```

---

## Task 3: Pydantic Models

**Files:**
- Create: `src/models/tenant.py`
- Create: `src/models/agent.py`
- Create: `src/models/skill.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: Write failing model tests**

```python
# tests/unit/test_models.py
import pytest
from src.models.tenant import TenantCreate, TenantResponse, UserCreate, UserResponse
from src.models.agent import AgentCreate, AgentResponse
from src.models.skill import SkillCreate, SkillResponse, SkillStatus, SkillScope

pytestmark = pytest.mark.unit


def test_tenant_create():
    t = TenantCreate(name="Test Store")
    assert t.name == "Test Store"
    assert t.config == {}


def test_tenant_response():
    import uuid
    tid = uuid.uuid4()
    t = TenantResponse(id=tid, name="Store A")
    assert t.id == tid


def test_user_create():
    u = UserCreate(id="user1", name="Alice", role="manager", tenant_id=__import__("uuid").uuid4())
    assert u.role == "manager"


def test_skill_status_values():
    assert SkillStatus.DRAFT == "draft"
    assert SkillStatus.PENDING == "pending"
    assert SkillStatus.APPROVED == "approved"
    assert SkillStatus.REJECTED == "rejected"
    assert SkillStatus.DISABLED == "disabled"


def test_skill_scope_values():
    assert SkillScope.SYSTEM == "system"
    assert SkillScope.TENANT == "tenant"


def test_skill_create_defaults():
    s = SkillCreate(name="test-skill", content="# Test")
    assert s.scope == SkillScope.TENANT
    assert s.status == SkillStatus.DRAFT


def test_agent_create():
    import uuid
    a = AgentCreate(tenant_id=uuid.uuid4(), name="my-agent", model="gpt-4o")
    assert a.temperature == 0.7
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement tenant models**

```python
# src/models/tenant.py
"""Tenant and user data models."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    config: dict = Field(default_factory=dict)


class TenantResponse(BaseModel):
    id: UUID
    name: str
    config: dict = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    id: str = Field(..., max_length=128)
    tenant_id: UUID
    name: str = Field(..., max_length=255)
    role: str = Field(default="staff", pattern="^(manager|staff|admin)$")
    channel_source: str = Field(default="console")


class UserResponse(BaseModel):
    id: str
    tenant_id: UUID
    name: str
    role: str
    channel_source: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement agent model**

```python
# src/models/agent.py
"""Agent configuration data models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    tenant_id: UUID
    name: str = Field(default="default", max_length=255)
    model: str = Field(default="gpt-4o")
    system_prompt: str = Field(default="You are a helpful store manager assistant.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    config: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    model: str
    system_prompt: str
    temperature: float
    config: dict
    enabled: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    config: dict | None = None
    enabled: bool | None = None
```

- [ ] **Step 5: Implement skill model**

```python
# src/models/skill.py
"""Skill metadata and workflow models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class SkillStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISABLED = "disabled"


class SkillScope(str, Enum):
    SYSTEM = "system"
    TENANT = "tenant"
    USER = "user"


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9_-]+$")
    scope: SkillScope = Field(default=SkillScope.TENANT)
    status: SkillStatus = Field(default=SkillStatus.DRAFT)
    content: str = Field(..., min_length=1)
    config: dict = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["all"])


class SkillResponse(BaseModel):
    id: UUID
    tenant_id: UUID | None = None
    name: str
    scope: SkillScope
    status: SkillStatus
    content: str
    created_by: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    config: dict
    channels: list[str]
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SkillUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    config: dict | None = None
    channels: list[str] | None = None


class SkillApprovalRequest(BaseModel):
    approved: bool
    rejection_reason: str | None = None
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_models.py -v
```

Expected: 7 PASSED

- [ ] **Step 7: Commit**

```bash
git add src/models/ tests/unit/test_models.py
git commit -m "feat: add Pydantic models for tenant, agent, skill"
```

---

## Task 4: Auth System

**Files:**
- Create: `src/auth.py`
- Create: `src/api/deps.py`
- Create: `src/api/auth_routes.py`
- Create: `tests/unit/test_auth.py`
- Create: `tests/integration/test_auth_api.py`

- [ ] **Step 1: Write failing auth unit tests**

```python
# tests/unit/test_auth.py
import os
import pytest
import jwt

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.unit


def test_create_token():
    from src.auth import create_token
    token = create_token(user_id="user1", tenant_id="tenant1")
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["sub"] == "user1"
    assert payload["tenant_id"] == "tenant1"


def test_verify_token_valid():
    from src.auth import create_token, verify_token
    token = create_token(user_id="user1", tenant_id="tenant1")
    payload = verify_token(token)
    assert payload["sub"] == "user1"


def test_verify_token_invalid():
    from src.auth import verify_token
    with pytest.raises(Exception):
        verify_token("invalid-token")


def test_verify_token_expired():
    from src.auth import verify_token
    import jwt as pyjwt
    token = pyjwt.encode(
        {"sub": "user1", "exp": 0},
        "test-secret",
        algorithm="HS256",
    )
    with pytest.raises(Exception):
        verify_token(token)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_auth.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement auth module**

```python
# src/auth.py
"""Multi-tenant authentication for LangGraph Server."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from langgraph_sdk import Auth

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))

auth = Auth()


def create_token(user_id: str, tenant_id: str) -> str:
    """Create a JWT token for a user."""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


@auth.authenticate
async def authenticate(headers: dict) -> str:
    """Extract user identity from JWT in Authorization header."""
    auth_header = headers.get(b"authorization", b"")
    if isinstance(auth_header, bytes):
        auth_header = auth_header.decode("utf-8")

    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Missing authorization token")

    try:
        payload = verify_token(token)
    except jwt.ExpiredSignatureError:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload["sub"]
```

- [ ] **Step 4: Run unit tests to verify they pass**

```bash
python -m pytest tests/unit/test_auth.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Implement API dependencies**

```python
# src/api/deps.py
"""FastAPI dependency functions for request context."""

from starlette.requests import Request

from src.auth import verify_token


async def get_current_user(request: Request) -> dict:
    """Extract current user from JWT token."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Missing authorization")
    return verify_token(token)


async def get_tenant_id(request: Request) -> str:
    """Extract tenant_id from the current user's token."""
    user = await get_current_user(request)
    return user["tenant_id"]
```

- [ ] **Step 6: Implement auth routes (login endpoint)**

```python
# src/api/auth_routes.py
"""Authentication API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.auth import create_token
from src.db.client import fetch_one

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    user_id: str
    channel_source: str = "console"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Login and receive a JWT token.

    In production this would verify credentials against an identity provider.
    For MVP, we look up the user in the DB by user_id + channel_source.
    """
    user = await fetch_one(
        "SELECT id, tenant_id::text, name, role FROM users "
        "WHERE id = $1 AND channel_source = $2",
        body.user_id,
        body.channel_source,
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token = create_token(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
    )
    return LoginResponse(
        access_token=token,
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )
```

- [ ] **Step 7: Write integration test for login**

```python
# tests/integration/test_auth_api.py
import os
import pytest
import httpx

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_login_flow():
    """Test the full login flow: create tenant+user, then login."""
    from src.db.client import execute, fetch_one
    from src.auth import create_token, verify_token
    import uuid

    # Setup: create tenant and user
    tenant_id = str(uuid.uuid4())
    await execute(
        "INSERT INTO tenants (id, name) VALUES ($1, $2)",
        tenant_id, "Auth Test Store"
    )
    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) "
        "VALUES ($1, $2, $3, $4, $5)",
        "auth-test-user", tenant_id, "Auth Tester", "manager", "console"
    )

    # Test token creation and verification
    token = create_token("auth-test-user", tenant_id)
    payload = verify_token(token)
    assert payload["sub"] == "auth-test-user"
    assert payload["tenant_id"] == tenant_id

    # Cleanup
    await execute("DELETE FROM users WHERE id = $1", "auth-test-user")
    await execute("DELETE FROM tenants WHERE id = $1", tenant_id)
```

- [ ] **Step 8: Run all auth tests**

```bash
python -m pytest tests/unit/test_auth.py tests/integration/test_auth_api.py -v
```

Expected: All PASSED

- [ ] **Step 9: Commit**

```bash
git add src/auth.py src/api/deps.py src/api/auth_routes.py tests/unit/test_auth.py tests/integration/test_auth_api.py
git commit -m "feat: add JWT auth system with LangGraph auth.path integration"
```

---

## Task 5: Checkpointer Factory

**Files:**
- Create: `src/checkpointer.py`
- Create: `tests/unit/test_checkpointer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_checkpointer.py
import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")

pytestmark = pytest.mark.unit


def test_create_checkpointer_returns_context_manager():
    """The factory should return an async context manager."""
    import inspect
    from src.checkpointer import create_checkpointer
    assert inspect.isasyncgenfunction(create_checkpointer) or callable(create_checkpointer)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_checkpointer.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement checkpointer factory**

```python
# src/checkpointer.py
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
```

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/unit/test_checkpointer.py -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add src/checkpointer.py tests/unit/test_checkpointer.py
git commit -m "feat: add PostgresSaver factory for LangGraph checkpointer"
```

---

## Task 6: Skill Parser (from QwenPaw)

**Files:**
- Create: `src/agent/skills.py`
- Create: `tests/unit/test_skill_parser.py`

- [ ] **Step 1: Write failing parser tests**

```python
# tests/unit/test_skill_parser.py
import pytest
from src.agent.skills import parse_skill_content, skill_to_tool

pytestmark = pytest.mark.unit


SAMPLE_SKILL_MD = """---
name: inventory_check
description: "Use this skill when the user asks about inventory levels or stock checks."
metadata:
  emoji: "📦"
---

# Inventory Check Skill

When the user asks about inventory, follow these steps:

1. Ask which product they want to check
2. Query the inventory system
3. Report current stock levels
"""


def test_parse_skill_content():
    name, description, body = parse_skill_content(SAMPLE_SKILL_MD)
    assert name == "inventory_check"
    assert "inventory" in description.lower()
    assert "# Inventory Check Skill" in body


def test_parse_skill_content_no_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill_content("No frontmatter here")


def test_parse_skill_content_missing_name():
    bad = "---\ndescription: test\n---\nbody"
    with pytest.raises(ValueError, match="name"):
        parse_skill_content(bad)


def test_skill_to_tool():
    from src.models.skill import SkillResponse, SkillStatus, SkillScope
    from uuid import uuid4

    skill = SkillResponse(
        id=uuid4(),
        tenant_id=uuid4(),
        name="test-skill",
        scope=SkillScope.TENANT,
        status=SkillStatus.APPROVED,
        content=SAMPLE_SKILL_MD,
        config={},
        channels=["all"],
        version=1,
    )
    tool = skill_to_tool(skill)
    assert tool.name == "inventory_check"
    assert "inventory" in tool.description.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_skill_parser.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement skill parser**

```python
# src/agent/skills.py
"""Parse SKILL.md files and convert to LangGraph tools.

Reuses QwenPaw's SKILL.md format: YAML frontmatter + Markdown body.
"""

import re
from typing import Any

import yaml
from langchain_core.tools import StructuredTool, BaseTool

from src.models.skill import SkillResponse


def parse_skill_content(content: str) -> tuple[str, str, str]:
    """Parse SKILL.md content into (name, description, body).

    Args:
        content: Full SKILL.md file content with YAML frontmatter.

    Returns:
        Tuple of (name, description, markdown_body).

    Raises:
        ValueError: If frontmatter is missing or invalid.
    """
    # Match YAML frontmatter between --- markers
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md must contain YAML frontmatter between --- markers")

    frontmatter_str = match.group(1)
    body = match.group(2).strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")

    if not isinstance(frontmatter, dict):
        raise ValueError("Frontmatter must be a YAML mapping")

    name = frontmatter.get("name")
    if not name:
        raise ValueError("SKILL.md frontmatter must include 'name' field")

    description = frontmatter.get("description", "")

    return name, description, body


def skill_to_tool(skill: SkillResponse) -> BaseTool:
    """Convert a SkillResponse to a LangChain/LangGraph tool.

    The tool provides the skill's instructions as context to the agent
    when invoked.
    """
    name, description, body = parse_skill_content(skill.content)

    def execute_skill(query: str) -> str:
        """Execute the skill with the given user query."""
        return (
            f"## Skill: {name}\n\n"
            f"### Instructions\n{body}\n\n"
            f"### User Query\n{query}\n\n"
            f"Please follow the skill instructions above to answer the user's query."
        )

    return StructuredTool.from_function(
        func=execute_skill,
        name=name,
        description=description or f"Skill: {name}",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_skill_parser.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/agent/__init__.py src/agent/skills.py tests/unit/test_skill_parser.py
git commit -m "feat: add SKILL.md parser and skill-to-tool converter"
```

---

## Task 7: Agent Graph Factory

**Files:**
- Create: `src/agent/graph.py`
- Create: `src/agent/tools.py`
- Create: `tests/unit/test_graph_factory.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_graph_factory.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_graph_factory.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement built-in tools**

```python
# src/agent/tools.py
"""Built-in tools and dynamic tool loading for the agent."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from src.db.client import fetch_all
from src.agent.skills import skill_to_tool
from src.models.skill import SkillResponse, SkillStatus, SkillScope


def get_builtin_tools() -> list[BaseTool]:
    """Return built-in tools available to all agents.

    MVP: minimal tool set. Add more from QwenPaw as needed.
    """

    @tool
    def get_current_time() -> str:
        """Get the current date and time."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    return [get_current_time]


async def load_tenant_skills(tenant_id: str) -> list[BaseTool]:
    """Load all enabled, approved skills for a tenant and convert to tools."""
    # Load system-level skills (tenant_id IS NULL)
    system_rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE scope = $1 AND status = $2",
        SkillScope.SYSTEM.value,
        SkillStatus.APPROVED.value,
    )

    # Load tenant-level skills
    tenant_rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE tenant_id = $1 AND status = $2",
        tenant_id,
        SkillStatus.APPROVED.value,
    )

    tools = []
    for row in system_rows + tenant_rows:
        try:
            skill = SkillResponse(**row)
            tools.append(skill_to_tool(skill))
        except Exception:
            # Skip malformed skills
            continue

    return tools


async def load_mcp_tools(tenant_id: str) -> list[BaseTool]:
    """Load MCP tools for a tenant. Placeholder for Phase 3."""
    return []
```

- [ ] **Step 4: Implement graph factory**

```python
# src/agent/graph.py
"""Dynamic agent graph factory for LangGraph Server.

Called on every Run with the current config. Builds a fresh
create_react_agent with the tenant's latest Skills/Tools/MCP.
"""

import os
from typing import Any

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agent.tools import get_builtin_tools, load_tenant_skills, load_mcp_tools
from src.db.client import fetch_one


def _get_default_model():
    """Get the default chat model. Uses ChatOpenAI as default."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=os.environ.get("DEFAULT_MODEL", "gpt-4o"),
        temperature=0.7,
    )


async def make_graph(config: dict, runtime: Any = None):
    """Build agent graph dynamically per-request.

    Referenced by langgraph.json graphs config.
    LangGraph Server calls this factory on every Run creation.

    Args:
        config: Run config with configurable containing tenant_id.
        runtime: LangGraph ServerRuntime with store access.
    """
    configurable = config.get("configurable", {})
    tenant_id = configurable.get("tenant_id")

    # Load tenant's agent config
    agent_config = None
    if tenant_id:
        agent_config = await fetch_one(
            "SELECT model, system_prompt, temperature, config FROM agents "
            "WHERE tenant_id = $1 AND enabled = true LIMIT 1",
            tenant_id,
        )

    # Determine model
    if agent_config:
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(
            model=agent_config["model"],
            temperature=agent_config["temperature"],
        )
        system_prompt = agent_config["system_prompt"]
    else:
        model = _get_default_model()
        system_prompt = "You are a helpful store manager assistant."

    # Load tools dynamically
    tools = get_builtin_tools()
    if tenant_id:
        tools.extend(await load_tenant_skills(tenant_id))
        tools.extend(await load_mcp_tools(tenant_id))

    # Build the agent
    graph = create_react_agent(
        model=model,
        tools=tools if tools else None,
        prompt=system_prompt,
    )

    return graph
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_graph_factory.py -v
```

Expected: All PASSED

- [ ] **Step 6: Commit**

```bash
git add src/agent/graph.py src/agent/tools.py tests/unit/test_graph_factory.py
git commit -m "feat: add dynamic agent graph factory with skill/tool loading"
```

---

## Task 8: Custom App Base + Tenant API

**Files:**
- Create: `src/custom_app.py`
- Create: `src/api/tenants.py`
- Create: `tests/integration/test_tenant_api.py`

- [ ] **Step 1: Write failing tenant API tests**

```python
# tests/integration/test_tenant_api.py
import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.integration


@pytest.fixture
def app():
    from src.custom_app import app
    return app


@pytest.fixture
def client(app):
    from starlette.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create a test tenant+user and return auth headers."""
    import asyncio
    from src.auth import create_token
    from src.db.client import execute
    import uuid

    tenant_id = str(uuid.uuid4())
    asyncio.get_event_loop().run_until_complete(
        execute("INSERT INTO tenants (id, name) VALUES ($1, $2)", tenant_id, "API Test Store")
    )
    asyncio.get_event_loop().run_until_complete(
        execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) "
            "VALUES ($1, $2, $3, $4, $5)",
            "api-test-user", tenant_id, "API Tester", "manager", "console"
        )
    )
    token = create_token("api-test-user", tenant_id)
    yield {"authorization": f"Bearer {token}"}, tenant_id
    # Cleanup
    asyncio.get_event_loop().run_until_complete(
        execute("DELETE FROM users WHERE id = $1", "api-test-user")
    )
    asyncio.get_event_loop().run_until_complete(
        execute("DELETE FROM tenants WHERE id = $1", tenant_id)
    )


def test_create_tenant(client, auth_headers):
    headers, _ = auth_headers
    resp = client.post("/api/tenants", json={"name": "New Store"}, headers=headers)
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "New Store"
    assert "id" in data


def test_list_tenants(client, auth_headers):
    headers, tenant_id = auth_headers
    resp = client.get("/api/tenants", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(t["id"] == tenant_id for t in data)


def test_unauthorized_access(client):
    resp = client.get("/api/tenants")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/integration/test_tenant_api.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement tenant API routes**

```python
# src/api/tenants.py
"""Tenant management API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from starlette.requests import Request

from src.api.deps import get_current_user, get_tenant_id
from src.db.client import execute, fetch_all, fetch_one
from src.models.tenant import TenantCreate, TenantResponse

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def list_tenants(user: dict = Depends(get_current_user)):
    """List tenants accessible to the current user."""
    # For MVP: return user's own tenant
    rows = await fetch_all(
        "SELECT id, name, config, created_at FROM tenants WHERE id = $1",
        user["tenant_id"],
    )
    return [TenantResponse(**row) for row in rows]


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(body: TenantCreate, user: dict = Depends(get_current_user)):
    """Create a new tenant."""
    row = await fetch_one(
        "INSERT INTO tenants (name, config) VALUES ($1, $2) "
        "RETURNING id, name, config, created_at",
        body.name,
        str(body.config) if body.config else "{}",
    )
    # Also create the requesting user as manager of this tenant
    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) "
        "VALUES ($1, $2, $3, $4, $5) "
        "ON CONFLICT (channel_source, id) DO NOTHING",
        user["sub"],
        str(row["id"]),
        "System",
        "manager",
        "console",
    )
    return TenantResponse(**row)
```

- [ ] **Step 4: Implement custom app**

```python
# src/custom_app.py
"""FastAPI custom app mounted into LangGraph Server via http.app config.

All custom business logic routes are defined here.
"""

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

# Import and register routers
from src.api.tenants import router as tenants_router
from src.api.auth_routes import router as auth_router

app.include_router(tenants_router)
app.include_router(auth_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/integration/test_tenant_api.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/custom_app.py src/api/tenants.py tests/integration/test_tenant_api.py
git commit -m "feat: add custom FastAPI app with tenant management API"
```

---

## Task 9: Skill API + Approval Workflow

**Files:**
- Create: `src/api/skills.py`
- Create: `tests/integration/test_skill_api.py`

- [ ] **Step 1: Write failing skill API tests**

```python
# tests/integration/test_skill_api.py
import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.integration


@pytest.fixture
def setup_tenant():
    """Create a test tenant with manager and admin users."""
    import asyncio
    from src.auth import create_token
    from src.db.client import execute
    import uuid

    tenant_id = str(uuid.uuid4())

    async def _setup():
        await execute("INSERT INTO tenants (id, name) VALUES ($1, $2)", tenant_id, "Skill Test Store")
        await execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES ($1,$2,$3,$4,$5)",
            "skill-mgr", tenant_id, "Manager", "manager", "console"
        )
        await execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES ($1,$2,$3,$4,$5)",
            "skill-admin", tenant_id, "Admin", "admin", "console"
        )

    asyncio.get_event_loop().run_until_complete(_setup())

    mgr_token = create_token("skill-mgr", tenant_id)
    admin_token = create_token("skill-admin", tenant_id)

    yield {
        "tenant_id": tenant_id,
        "mgr_headers": {"authorization": f"Bearer {mgr_token}"},
        "admin_headers": {"authorization": f"Bearer {admin_token}"},
    }

    async def _cleanup():
        await execute("DELETE FROM skills_meta WHERE tenant_id = $1", tenant_id)
        await execute("DELETE FROM users WHERE tenant_id = $1", tenant_id)
        await execute("DELETE FROM tenants WHERE id = $1", tenant_id)

    asyncio.get_event_loop().run_until_complete(_cleanup())


@pytest.fixture
def client():
    from src.custom_app import app
    from starlette.testclient import TestClient
    return TestClient(app)


def test_create_skill(client, setup_tenant):
    headers = setup_tenant["mgr_headers"]
    resp = client.post("/api/skills", json={
        "name": "test-skill",
        "content": "---\nname: test-skill\ndescription: Test\n---\n# Test Skill",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-skill"
    assert data["status"] == "draft"


def test_skill_approval_workflow(client, setup_tenant):
    """Test: create → submit → approve flow."""
    mgr = setup_tenant["mgr_headers"]
    admin = setup_tenant["admin_headers"]

    # 1. Manager creates skill
    resp = client.post("/api/skills", json={
        "name": "approval-test",
        "content": "---\nname: approval-test\ndescription: Approval test\n---\n# Test",
    }, headers=mgr)
    assert resp.status_code == 201
    skill_id = resp.json()["id"]

    # 2. Manager submits for approval
    resp = client.post(f"/api/skills/{skill_id}/submit", headers=mgr)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    # 3. Admin approves
    resp = client.post(f"/api/skills/{skill_id}/approve", headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_skill_rejection(client, setup_tenant):
    """Test: create → submit → reject flow."""
    mgr = setup_tenant["mgr_headers"]
    admin = setup_tenant["admin_headers"]

    resp = client.post("/api/skills", json={
        "name": "reject-test",
        "content": "---\nname: reject-test\ndescription: Will be rejected\n---\n# Test",
    }, headers=mgr)
    skill_id = resp.json()["id"]

    client.post(f"/api/skills/{skill_id}/submit", headers=mgr)

    resp = client.post(f"/api/skills/{skill_id}/reject", json={
        "rejection_reason": "Not relevant"
    }, headers=admin)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["rejection_reason"] == "Not relevant"


def test_list_pending_skills(client, setup_tenant):
    """Admin can list pending skills."""
    mgr = setup_tenant["mgr_headers"]
    admin = setup_tenant["admin_headers"]

    client.post("/api/skills", json={
        "name": "pending-list-test",
        "content": "---\nname: pending-list-test\ndescription: test\n---\n# Test",
    }, headers=mgr)

    resp = client.get("/api/skills/pending", headers=admin)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/integration/test_skill_api.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement skill API routes**

```python
# src/api/skills.py
"""Skill management API with approval workflow."""

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from src.api.deps import get_current_user, get_tenant_id
from src.db.client import execute, fetch_all, fetch_one
from src.models.skill import (
    SkillCreate, SkillResponse, SkillUpdate,
    SkillStatus, SkillScope, SkillApprovalRequest,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillResponse])
async def list_skills(user: dict = Depends(get_current_user)):
    """List all skills for the current tenant."""
    rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE tenant_id = $1 OR scope = 'system' "
        "ORDER BY created_at DESC",
        user["tenant_id"],
    )
    return [SkillResponse(**r) for r in rows]


@router.post("", response_model=SkillResponse, status_code=201)
async def create_skill(body: SkillCreate, user: dict = Depends(get_current_user)):
    """Create a new skill (status=draft)."""
    row = await fetch_one(
        "INSERT INTO skills_meta (tenant_id, name, scope, status, content, created_by, config, channels) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
        "RETURNING *",
        user["tenant_id"],
        body.name,
        body.scope.value,
        SkillStatus.DRAFT.value,
        body.content,
        user["sub"],
        str(body.config),
        str(body.channels),
    )
    return SkillResponse(**row)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str, body: SkillUpdate, user: dict = Depends(get_current_user)
):
    """Update a skill (only draft or rejected skills can be edited)."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = $1", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] not in (SkillStatus.DRAFT.value, SkillStatus.REJECTED.value):
        raise HTTPException(400, "Only draft or rejected skills can be edited")

    updates = []
    params = []
    idx = 1
    if body.name is not None:
        updates.append(f"name = ${idx}")
        params.append(body.name)
        idx += 1
    if body.content is not None:
        updates.append(f"content = ${idx}")
        params.append(body.content)
        idx += 1
    if body.config is not None:
        updates.append(f"config = ${idx}")
        params.append(str(body.config))
        idx += 1

    if not updates:
        return SkillResponse(**skill)

    updates.append(f"updated_at = NOW()")
    params.append(skill_id)

    row = await fetch_one(
        f"UPDATE skills_meta SET {', '.join(updates)} WHERE id = ${idx} RETURNING *",
        *params,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/submit", response_model=SkillResponse)
async def submit_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Submit a draft skill for approval."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = $1", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] not in (SkillStatus.DRAFT.value, SkillStatus.REJECTED.value):
        raise HTTPException(400, "Only draft or rejected skills can be submitted")

    row = await fetch_one(
        "UPDATE skills_meta SET status = $1, updated_at = NOW() WHERE id = $2 RETURNING *",
        SkillStatus.PENDING.value,
        skill_id,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/approve", response_model=SkillResponse)
async def approve_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Approve a pending skill (admin only)."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = $1", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] != SkillStatus.PENDING.value:
        raise HTTPException(400, "Only pending skills can be approved")

    row = await fetch_one(
        "UPDATE skills_meta SET status = $1, approved_by = $2, approved_at = NOW(), "
        "updated_at = NOW() WHERE id = $3 RETURNING *",
        SkillStatus.APPROVED.value,
        user["sub"],
        skill_id,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/reject", response_model=SkillResponse)
async def reject_skill(
    skill_id: str,
    body: SkillApprovalRequest,
    user: dict = Depends(get_current_user),
):
    """Reject a pending skill (admin only)."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = $1", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] != SkillStatus.PENDING.value:
        raise HTTPException(400, "Only pending skills can be rejected")

    row = await fetch_one(
        "UPDATE skills_meta SET status = $1, approved_by = $2, "
        "rejection_reason = $3, updated_at = NOW() WHERE id = $4 RETURNING *",
        SkillStatus.REJECTED.value,
        user["sub"],
        body.rejection_reason,
        skill_id,
    )
    return SkillResponse(**row)


@router.post("/{skill_id}/enable", response_model=SkillResponse)
async def enable_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Enable an approved skill."""
    row = await fetch_one(
        "UPDATE skills_meta SET status = $1, updated_at = NOW() WHERE id = $2 RETURNING *",
        SkillStatus.APPROVED.value,
        skill_id,
    )
    if not row:
        raise HTTPException(404, "Skill not found")
    return SkillResponse(**row)


@router.post("/{skill_id}/disable", response_model=SkillResponse)
async def disable_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Disable a skill."""
    row = await fetch_one(
        "UPDATE skills_meta SET status = $1, updated_at = NOW() WHERE id = $2 RETURNING *",
        SkillStatus.DISABLED.value,
        skill_id,
    )
    if not row:
        raise HTTPException(404, "Skill not found")
    return SkillResponse(**row)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str, user: dict = Depends(get_current_user)):
    """Delete a disabled skill."""
    skill = await fetch_one("SELECT * FROM skills_meta WHERE id = $1", skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")
    if skill["status"] != SkillStatus.DISABLED.value:
        raise HTTPException(400, "Only disabled skills can be deleted")
    await execute("DELETE FROM skills_meta WHERE id = $1", skill_id)
    return {"detail": "Deleted"}


@router.get("/pending", response_model=list[SkillResponse])
async def list_pending_skills(user: dict = Depends(get_current_user)):
    """List all pending skills (admin view)."""
    rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE status = $1 ORDER BY updated_at DESC",
        SkillStatus.PENDING.value,
    )
    return [SkillResponse(**r) for r in rows]


@router.get("/system", response_model=list[SkillResponse])
async def list_system_skills(user: dict = Depends(get_current_user)):
    """List system-level skills (read-only)."""
    rows = await fetch_all(
        "SELECT * FROM skills_meta WHERE scope = $1 ORDER BY name",
        SkillScope.SYSTEM.value,
    )
    return [SkillResponse(**r) for r in rows]
```

- [ ] **Step 4: Register skill router in custom_app.py**

Add to `src/custom_app.py`:

```python
from src.api.skills import router as skills_router
app.include_router(skills_router)
```

- [ ] **Step 5: Run all skill tests**

```bash
python -m pytest tests/integration/test_skill_api.py -v
```

Expected: All PASSED

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All PASSED

- [ ] **Step 7: Commit**

```bash
git add src/api/skills.py src/custom_app.py tests/integration/test_skill_api.py
git commit -m "feat: add skill CRUD API with approval workflow"
```

---

## Task 10: Agent Config API

**Files:**
- Create: `src/api/agents.py`
- Create: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_agent_api.py
import os
import pytest

os.environ.setdefault("DATABASE_URI", "postgresql://storeagent:storeagent@localhost:5432/storeagent")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.integration


@pytest.fixture
def setup():
    import asyncio
    from src.auth import create_token
    from src.db.client import execute
    import uuid

    tenant_id = str(uuid.uuid4())

    async def _setup():
        await execute("INSERT INTO tenants (id, name) VALUES ($1, $2)", tenant_id, "Agent Test")
        await execute(
            "INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES ($1,$2,$3,$4,$5)",
            "agent-user", tenant_id, "User", "manager", "console"
        )

    asyncio.get_event_loop().run_until_complete(_setup())
    token = create_token("agent-user", tenant_id)
    yield {"authorization": f"Bearer {token}"}, tenant_id

    async def _cleanup():
        await execute("DELETE FROM agents WHERE tenant_id = $1", tenant_id)
        await execute("DELETE FROM users WHERE tenant_id = $1", tenant_id)
        await execute("DELETE FROM tenants WHERE id = $1", tenant_id)

    asyncio.get_event_loop().run_until_complete(_cleanup())


@pytest.fixture
def client():
    from src.custom_app import app
    from starlette.testclient import TestClient
    return TestClient(app)


def test_create_agent(client, setup):
    headers, _ = setup
    resp = client.post("/api/agents", json={
        "name": "store-helper",
        "model": "gpt-4o",
        "system_prompt": "You help with store operations.",
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "store-helper"


def test_get_agent(client, setup):
    headers, _ = setup
    # Create
    resp = client.post("/api/agents", json={"name": "get-test"}, headers=headers)
    agent_id = resp.json()["id"]
    # Get
    resp = client.get(f"/api/agents/{agent_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-test"


def test_update_agent(client, setup):
    headers, _ = setup
    resp = client.post("/api/agents", json={"name": "update-test"}, headers=headers)
    agent_id = resp.json()["id"]
    resp = client.put(f"/api/agents/{agent_id}", json={
        "system_prompt": "Updated prompt",
        "temperature": 0.5,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["system_prompt"] == "Updated prompt"
    assert resp.json()["temperature"] == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/integration/test_agent_api.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement agent API**

```python
# src/api/agents.py
"""Agent configuration API routes."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user
from src.db.client import execute, fetch_all, fetch_one
from src.models.agent import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentResponse])
async def list_agents(user: dict = Depends(get_current_user)):
    rows = await fetch_all(
        "SELECT * FROM agents WHERE tenant_id = $1 ORDER BY created_at",
        user["tenant_id"],
    )
    return [AgentResponse(**r) for r in rows]


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(body: AgentCreate, user: dict = Depends(get_current_user)):
    body.tenant_id = __import__("uuid").UUID(user["tenant_id"])
    row = await fetch_one(
        "INSERT INTO agents (tenant_id, name, model, system_prompt, temperature, config) "
        "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
        user["tenant_id"], body.name, body.model, body.system_prompt,
        body.temperature, str(body.config),
    )
    return AgentResponse(**row)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, user: dict = Depends(get_current_user)):
    row = await fetch_one(
        "SELECT * FROM agents WHERE id = $1 AND tenant_id = $2",
        agent_id, user["tenant_id"],
    )
    if not row:
        raise HTTPException(404, "Agent not found")
    return AgentResponse(**row)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str, body: AgentUpdate, user: dict = Depends(get_current_user)
):
    existing = await fetch_one(
        "SELECT * FROM agents WHERE id = $1 AND tenant_id = $2",
        agent_id, user["tenant_id"],
    )
    if not existing:
        raise HTTPException(404, "Agent not found")

    updates = []
    params = []
    idx = 1
    for field in ("name", "model", "system_prompt", "temperature", "config", "enabled"):
        val = getattr(body, field, None)
        if val is not None:
            updates.append(f"{field} = ${idx}")
            params.append(str(val) if isinstance(val, dict) else val)
            idx += 1

    if not updates:
        return AgentResponse(**existing)

    params.append(agent_id)
    row = await fetch_one(
        f"UPDATE agents SET {', '.join(updates)} WHERE id = ${idx} RETURNING *",
        *params,
    )
    return AgentResponse(**row)
```

- [ ] **Step 4: Register agent router in custom_app.py**

Add to `src/custom_app.py`:

```python
from src.api.agents import router as agents_router
app.include_router(agents_router)
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All PASSED

- [ ] **Step 6: Commit**

```bash
git add src/api/agents.py src/custom_app.py tests/integration/test_agent_api.py
git commit -m "feat: add agent configuration CRUD API"
```

---

## Task 11: Verify LangGraph Server Starts

**Files:**
- Verify: `langgraph.json`, all `src/` modules

- [ ] **Step 1: Run migrations on clean DB**

```bash
make db-up
make migrate
```

- [ ] **Step 2: Seed a test tenant and user**

```bash
python -c "
import asyncio
from src.db.client import execute

async def seed():
    import uuid
    tid = str(uuid.uuid4())
    await execute('INSERT INTO tenants (id, name) VALUES (\$1, \$2)', tid, 'Demo Store')
    await execute(
        'INSERT INTO users (id, tenant_id, name, role, channel_source) VALUES (\$1,\$2,\$3,\$4,\$5)',
        'demo-user', tid, 'Demo Manager', 'manager', 'console'
    )
    await execute(
        'INSERT INTO agents (tenant_id, name, model, system_prompt) VALUES (\$1,\$2,\$3,\$4)',
        tid, 'default', 'gpt-4o', 'You are a helpful store manager assistant for Demo Store.'
    )
    print(f'Seeded tenant: {tid}')
    print(f'Seeded user: demo-user')

asyncio.run(seed())
"
```

- [ ] **Step 3: Start LangGraph dev server**

```bash
make dev
```

Expected: Server starts at `http://localhost:8123` without errors. The custom app routes and auth are loaded.

- [ ] **Step 4: Test native API health**

Open a new terminal:

```bash
curl http://localhost:8123/ok
```

Expected: `200 OK`

- [ ] **Step 5: Test custom API with token**

```bash
# Get a token via login endpoint (or create one manually)
python -c "from src.auth import create_token; print(create_token('demo-user', '<tenant_id>'))"
# Use the token to hit a custom endpoint
curl -H "Authorization: Bearer <token>" http://localhost:8123/api/tenants
```

Expected: JSON array with the demo tenant.

- [ ] **Step 6: Stop server and commit**

```bash
# Ctrl+C to stop server
git add -A
git commit -m "chore: verify langgraph dev server starts with custom app"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Project scaffolding | - |
| 2 | DB client + migrations | 5 integration tests |
| 3 | Pydantic models | 7 unit tests |
| 4 | Auth system | 4 unit + 1 integration |
| 5 | Checkpointer factory | 1 unit test |
| 6 | Skill parser | 4 unit tests |
| 7 | Agent graph factory | 2 unit tests |
| 8 | Custom app + Tenant API | 3 integration tests |
| 9 | Skill API + approval | 4 integration tests |
| 10 | Agent config API | 3 integration tests |
| 11 | Server verification | Manual smoke test |

**Total: ~34 tests, 11 tasks**

After completing Phase 1, proceed to Phase 2 (Channel + DingTalk) with a new plan.
