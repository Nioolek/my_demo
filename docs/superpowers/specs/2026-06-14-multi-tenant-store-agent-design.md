# Multi-Tenant Store Manager Agent Platform - Design Spec

**Date:** 2026-06-14
**Status:** Approved
**Author:** Huawei Terminal BG Development Team

## 1. Overview

Build a multi-tenant AI agent platform for Huawei retail store managers. Each store gets its own agent instance with independent conversation management, memory, skills, and channel integrations. The platform is built on **LangGraph Server** (via `pip install langgraph-api`) with QwenPaw components reused for Skills, Tools, and Channels.

### Key Concepts

| Field | Description |
|-------|-------------|
| `agent_id` | Identifies the current agent (one per tenant/store) |
| `user_id` | Current user ID, maps to their store via DB lookup |
| `thread_id` | Conversation thread ID, consistent across multi-turn dialogues |

### Core Requirements

1. Store managers can provision agents with tenant-scoped session/memory management
2. Skills support layered governance: system-level, tenant-level, with approval workflow
3. Channel abstraction layer with DingTalk as primary channel; LangGraph native streaming APIs preserved
4. External MCP server integration
5. Cron scheduled tasks that proactively push to user channels (DingTalk)
6. Unified management console (forked from QwenPaw Console)

---

## 2. Architecture

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Orchestration | LangGraph `create_react_agent` (from `langgraph-prebuilt`) |
| Server | `langgraph-api` v0.10+ (Starlette-based, pip installable) |
| Custom Business Logic | FastAPI app mounted via `http.app` config |
| Auth | LangGraph `auth.path` with custom `Auth()` instance |
| Database | PostgreSQL (Docker), shared with `langgraph-checkpoint-postgres` |
| Frontend | React 18 + Ant Design + TypeScript (forked QwenPaw Console) |
| Channel | Custom BaseChannel abstraction (modeled after QwenPaw) |
| Primary Channel | DingTalk bot |
| Python | 3.13 (project `.venv/`) |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                Frontend (Fork QwenPaw Console)               │
│         React 18 + Ant Design + TypeScript + Vite           │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ Tenant   │ Agent    │ Skill    │ Channel  │ Cron     │  │
│  │ Manager  │ Config   │ Approval │ Config   │ Manager  │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
├─────────────────────────────────────────────────────────────┤
│              LangGraph Server (langgraph_api)                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Native API: /threads  /runs  /assistants  /crons      │  │
│  │             /store    /mcp   /info   SSE streaming    │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ Custom App (http.app → FastAPI)                       │  │
│  │  /api/tenants/*     /api/skills/*    /api/channels/*  │  │
│  │  /api/mcp/*         /api/cron-jobs/*                   │  │
│  │  /webhooks/dingtalk /webhooks/internal/cron-callback   │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ Auth Layer (auth.path)                                │  │
│  │  JWT verification → user_id → tenant_id → filtering   │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ Agent Graph Factory (graphs config)                   │  │
│  │  make_graph(config) → create_react_agent              │  │
│  │  + QPaw Skills (as Tools) + QPaw Tools + MCP Tools    │  │
│  │  + PostgresSaver (checkpointer) + PostgresStore       │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    PostgreSQL (Docker)                        │
│  LangGraph native: checkpoints, checkpoint_blobs, store     │
│  Business: tenants, users, agents, skills_meta, channels,   │
│            mcp_servers, cron_jobs_meta, threads_meta         │
└─────────────────────────────────────────────────────────────┘
```

### Deployment

- **Development:** `langgraph dev` (auto-reload, in-memory or PG)
- **Production:** `langgraph up` (Docker) or direct `uvicorn` with `langgraph_api`
- **Database:** PostgreSQL via Docker Compose

### langgraph.json Configuration

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
    "path": "./src/checkpointer.py:create_checkpointer",
    "ttl": {
      "strategy": "keep_latest",
      "default_ttl": 43200,
      "sweep_interval_minutes": 60
    }
  }
}
```

---

## 3. Data Model

### Multi-Tenant Isolation

Logical isolation via `tenant_id` foreign keys on all business tables. Single shared PostgreSQL database.

### LangGraph Native Tables (auto-managed)

- `checkpoints` — graph state snapshots (thread_id, checkpoint, metadata)
- `checkpoint_blobs` — binary data storage
- `checkpoint_writes` — write-ahead log
- `checkpoint_migrations` — schema version tracking
- `store` — cross-thread key-value memory (namespace, key, value, ttl_minutes, expires_at)

### Business Tables

```sql
-- Tenants (stores)
tenants (
    id              UUID PRIMARY KEY,
    name            VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    config          JSONB DEFAULT '{}'
);

-- Users (store managers/staff)
users (
    id              VARCHAR(128) PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),
    name            VARCHAR(255),
    role            VARCHAR(50),           -- 'manager' | 'staff' | 'admin'
    channel_source  VARCHAR(50),           -- 'dingtalk' | 'console'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel_source, id)
);

-- Agent configuration (one per tenant)
agents (
    id              UUID PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),
    name            VARCHAR(255),
    model           VARCHAR(255),
    system_prompt   TEXT,
    temperature     FLOAT DEFAULT 0.7,
    config          JSONB DEFAULT '{}',
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Skill metadata with approval workflow
skills_meta (
    id              UUID PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),  -- NULL for system-level skills
    name            VARCHAR(255),
    scope           VARCHAR(50),           -- 'system' | 'tenant' | 'user'
    status          VARCHAR(50),           -- 'draft' | 'pending' | 'approved' | 'rejected' | 'disabled'
    content         TEXT,                   -- SKILL.md content
    created_by      VARCHAR(128) REFERENCES users(id),
    approved_by     VARCHAR(128),
    approved_at     TIMESTAMPTZ,
    rejection_reason TEXT,
    config          JSONB DEFAULT '{}',
    channels        JSONB DEFAULT '["all"]',
    version         INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Channel configuration
channels (
    id              UUID PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),
    agent_id        UUID REFERENCES agents(id),
    channel_type    VARCHAR(50),           -- 'dingtalk' | 'console'
    config          JSONB,
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, channel_type)
);

-- MCP server configuration
mcp_servers (
    id              UUID PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),  -- NULL for system-level MCP
    name            VARCHAR(255),
    transport       VARCHAR(50),           -- 'stdio' | 'sse' | 'streamable_http'
    url             TEXT,
    command         TEXT,
    args            JSONB DEFAULT '[]',
    env             JSONB DEFAULT '{}',
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Cron job metadata (extends LangGraph native cron)
cron_jobs_meta (
    id              UUID PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),
    agent_id        UUID REFERENCES agents(id),
    lg_cron_id      VARCHAR(255),          -- LangGraph native cron_id
    name            VARCHAR(255),
    description     TEXT,
    schedule        VARCHAR(255),
    timezone        VARCHAR(100) DEFAULT 'Asia/Shanghai',
    input_template  JSONB,
    enabled         BOOLEAN DEFAULT TRUE,
    created_by      VARCHAR(128) REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Thread metadata (extends LangGraph native threads)
threads_meta (
    thread_id       VARCHAR(255) PRIMARY KEY,
    tenant_id       UUID REFERENCES tenants(id),
    agent_id        UUID REFERENCES agents(id),
    user_id         VARCHAR(128) REFERENCES users(id),
    channel_type    VARCHAR(50),
    title           VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Thread ID Convention

```
thread_id = "{tenant_id}:{user_id}:{channel}:{session_id}"
```

This ensures global uniqueness while encoding routing information. Parsed by cron webhook callback to route responses back to the correct channel.

---

## 4. Agent & LangGraph Integration

### Dynamic Graph Factory

LangGraph Server natively supports graph factories that are called on every run. The factory receives the run config (containing `tenant_id` in `configurable`) and builds a fresh agent with the tenant's current Skills/Tools/MCP.

```python
# src/agent/graph.py
from langgraph.prebuilt import create_react_agent
from langgraph_api.schema import Config
from langgraph_sdk.runtime import ServerRuntime

def make_graph(config: Config, runtime: ServerRuntime):
    """Called on every Run. Builds agent with tenant's latest config."""
    tenant_id = config["configurable"]["tenant_id"]
    tenant_config = await get_tenant_config(tenant_id)

    tools = []
    tools.extend(await load_tenant_skills(tenant_id))   # Current enabled skills
    tools.extend(await load_mcp_tools(tenant_id))       # Current MCP servers
    tools.extend(get_builtin_tools())                    # Built-in tools

    return create_react_agent(
        model=get_model(tenant_config),
        tools=tools,
        prompt=tenant_config["system_prompt"],
        checkpointer=checkpointer,
        store=runtime.store,
    )
```

### Source Verification

Confirmed from `langgraph_api/_factory_utils.py`:
- `GraphValue = Pregel | GraphFactory | GraphFactoryFromConfig`
- `invoke_factory()` is called per-run with current config
- Factory supports 4 signatures: 0-param, config-only, runtime-only, both

### Request Flow

```
User message (DingTalk/Console)
    ↓
Auth Middleware: token → user_id → tenant_id lookup
    ↓
Create Run:
  POST /threads/{thread_id}/runs
  config = {"configurable": {"tenant_id": "...", "user_id": "..."}}
    ↓
make_graph(config) called:
  1. Query tenant config from DB (real-time, no cache)
  2. Load enabled skills → convert to LangGraph tools
  3. Load MCP tools
  4. Build create_react_agent
    ↓
Agent executes ReAct loop with checkpointing
    ↓
Response: SSE streaming → Channel → User
```

---

## 5. Skill System

### Layered Architecture

| Layer | Scope | Creator | Approval | Storage |
|-------|-------|---------|----------|---------|
| System | All tenants | Platform admin | No (pre-approved) | Code repo + `skills_meta(scope='system')` |
| Tenant | Single tenant | Store manager | Yes (admin approves) | `skills_meta(scope='tenant')` + DB content |
| User | Single user | Individual | Reserved for future | Not implemented in MVP |

### Skill Approval Workflow

```
Manager creates skill (status=draft)
    ↓
Submits for approval (draft → pending)
    ↓
Admin reviews → approved / rejected (with reason)
    ↓
If approved: skill available in next Run (factory loads from DB)
If rejected: manager edits and resubmits
```

### Skill → LangGraph Tool Conversion

Reuses QwenPaw's SKILL.md parsing logic. Each approved skill becomes a `StructuredTool` in the LangGraph agent's tool set.

### Permission Matrix

| Role | Create | Edit | Submit | Approve | Enable/Disable | Delete |
|------|--------|------|--------|---------|---------------|--------|
| Manager | ✅ tenant | ✅ own | ✅ | ❌ | ❌ | ✅ disabled |
| Admin | ✅ any | ✅ any | ✅ | ✅ | ✅ | ✅ |
| Staff | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### API Endpoints (Custom App)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/skills` | GET | List tenant's skills |
| `/api/skills` | POST | Create skill (draft) |
| `/api/skills/{id}` | PUT | Edit (draft/rejected only) |
| `/api/skills/{id}/submit` | POST | Submit for approval |
| `/api/skills/{id}/approve` | POST | Approve (admin only) |
| `/api/skills/{id}/reject` | POST | Reject with reason (admin only) |
| `/api/skills/{id}/enable` | POST | Enable approved skill |
| `/api/skills/{id}/disable` | POST | Disable skill |
| `/api/skills/{id}` | DELETE | Delete (disabled only) |
| `/api/skills/system` | GET | List system skills (read-only) |
| `/api/skills/pending` | GET | Pending approval list (admin) |

---

## 6. Channel Layer

### Architecture

```
BaseChannel (abstract base, modeled after QwenPaw)
    ├── DingTalkChannel     ← MVP priority
    ├── ConsoleChannel      ← Dev/debug, frontend direct
    └── (Future: FeishuChannel, WeChatChannel...)
```

### BaseChannel Interface

```python
class BaseChannel(ABC):
    channel: str

    @abstractmethod
    async def start(self): ...

    @abstractmethod
    async def stop(self): ...

    @abstractmethod
    async def send(self, to_handle: str, text: str, meta: dict): ...

    @abstractmethod
    def parse_incoming(self, payload: dict) -> AgentRequest: ...

    async def process_message(self, payload: dict):
        """Unified message processing pipeline."""
        request = self.parse_incoming(payload)
        thread_id = build_thread_id(request.tenant_id, request.user_id,
                                     self.channel, request.session_id)

        async for event in client.runs.stream(
            thread_id=thread_id,
            assistant_id="store-agent",
            input={"messages": [{"role": "user", "content": request.content}]},
            config={"configurable": {"tenant_id": request.tenant_id}},
            stream_mode=["messages", "updates"],
        ):
            if event.event == "messages":
                await self.send_stream_delta(request, event.data)
            elif event.event == "end":
                await self.send_complete(request)
```

### DingTalk Implementation

- Parses incoming webhook payload: extracts `senderStaffId` as `user_id`
- Looks up user in DB to get `tenant_id`
- Creates run via LangGraph SDK
- Sends response via DingTalk API

### DingTalk Webhook Endpoint

```python
# src/custom_app.py
@app.post("/webhooks/dingtalk")
async def dingtalk_webhook(request: Request):
    payload = await request.json()
    if not verify_dingtalk_signature(request):
        raise HTTPException(403)
    channel = get_channel("dingtalk")
    asyncio.create_task(channel.process_message(payload))
    return {"success": True}
```

### Channel Manager

Central manager for outbound message routing (used by cron callback and internal dispatch):

```python
class ChannelManager:
    async def send(self, channel, user_id, text, meta=None): ...
    async def send_event(self, channel, user_id, session_id, event, meta=None): ...
```

---

## 7. MCP Integration

### Architecture

MCP servers are configured per-tenant and loaded dynamically in the graph factory. Uses `langchain-mcp-adapters` to convert MCP tools to LangChain tools.

### Transport Support

| Transport | Description |
|-----------|-------------|
| `sse` | Server-Sent Events HTTP endpoint |
| `streamable_http` | Streamable HTTP endpoint |
| `stdio` | Local process (for development) |

### API Endpoints (Custom App)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/mcp` | GET | List tenant's MCP servers |
| `/api/mcp` | POST | Add MCP server |
| `/api/mcp/{id}` | PUT | Update configuration |
| `/api/mcp/{id}` | DELETE | Remove MCP server |
| `/api/mcp/{id}/test` | POST | Test connection |
| `/api/mcp/{id}/tools` | GET | List tools provided by this MCP |

---

## 8. Cron Scheduled Tasks

### Approach: LangGraph Native Cron + Webhook Callback

Use LangGraph's built-in cron scheduler with webhook callback to push results to user channels.

### Flow

```
LangGraph Cron Scheduler fires
    ↓
Creates stateful Run on user's thread
    ↓
Agent executes (normal ReAct loop)
    ↓
Run completes → POST webhook to /webhooks/internal/cron-callback
    ↓
Custom App receives: {thread_id, run_id, status, outputs}
    ↓
Parse thread_id → tenant_id + user_id + channel + session_id
    ↓
Extract agent's final response from thread state
    ↓
ChannelManager.send(channel, user_id, response)
    ↓
User receives message in DingTalk
```

### Cron Job Types

| Type | Description | Example |
|------|-------------|---------|
| Reminder | Time-based notification | "Remind manager to check inventory at 9am" |
| Report | Periodic report generation | "Generate weekly sales summary every Monday 9am" |
| Inspection | Automated check | "Check competitor prices every 2 hours" |

### API Endpoints (Custom App)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cron-jobs` | GET | List tenant's cron jobs |
| `/api/cron-jobs` | POST | Create cron job (syncs with LG cron) |
| `/api/cron-jobs/{id}` | PUT | Update (syncs with LG cron) |
| `/api/cron-jobs/{id}` | DELETE | Delete (syncs with LG cron) |
| `/api/cron-jobs/{id}/toggle` | POST | Enable/disable |
| `/api/cron-jobs/{id}/history` | GET | Execution history |

### Webhook Callback Handler

```python
@app.post("/webhooks/internal/cron-callback")
async def cron_callback(request: Request):
    payload = await request.json()
    thread_id = payload["thread_id"]
    tenant_id, user_id, channel, session_id = parse_thread_id(thread_id)

    state = await lg_client.threads.get_state(thread_id)
    last_ai_message = get_last_ai_message(state)

    await channel_manager.send(
        channel=channel, user_id=user_id,
        text=last_ai_message,
        meta={"source": "cron", "cron_run_id": payload["run_id"]},
    )
```

---

## 9. Auth & Multi-Tenancy

### Auth Architecture

```python
# src/auth.py
from langgraph_sdk import Auth

auth = Auth()

@auth.authenticate
async def authenticate(headers: dict) -> str:
    """Extract user identity from JWT token."""
    token = headers.get(b"authorization", b"").decode().replace("Bearer ", "")
    user = await verify_jwt(token)
    return user["id"]

@auth.on
async def authorize_tenant(ctx, value):
    """Resource-level authorization: filter by tenant."""
    user = ctx.user
    tenant_id = await get_user_tenant(user.identity)
    return {"tenant_id": tenant_id}
```

### Token Sources

| Scenario | Token Source |
|----------|-------------|
| DingTalk | DingTalk OAuth → backend verification → internal JWT |
| Console | User login → JWT → stored in frontend → Authorization header |
| Service-to-service | Internal API key |

### Request Authorization Flow

```
Request arrives
    ↓
auth_first middleware
    ↓ @auth.authenticate: verify token → user_id
    ↓
LangGraph native API (/threads, /runs...)
    ↓ @auth.on: inject tenant_id filter
    ↓
Custom App API (/api/skills, /api/channels...)
    ↓ Extract user from request.scope["user"]
    ↓ Query DB for tenant_id
    ↓
Business logic (auto-scoped to tenant_id)
```

---

## 10. Frontend (Fork QwenPaw Console)

### Preserved from QwenPaw

- Overall layout (MainLayout + Header + Sidebar)
- Ant Design + Zustand state management
- API client layer architecture
- Routing structure (react-router-dom v7)
- Component patterns (Card/List/Drawer)

### Modifications and New Pages

| Page | Change |
|------|--------|
| **Tenant Switcher** | New: Header component, switches tenant context for all API calls |
| **Login** | New: JWT authentication page |
| **Agent Config** | Modified:对接 Custom App `/api/agents/*` |
| **Skill Management** | Rewritten: 对接 `/api/skills/*`, add approval workflow UI |
| **Channel Config** | Modified: 对接 Custom App, simplified to DingTalk + Console |
| **MCP Management** | Modified: 对接 Custom App `/api/mcp/*` |
| **Cron Management** | Modified: Add dispatch target selector, 对接 `/api/cron-jobs/*` |
| **Chat/Test** | Preserved: Direct对接 LangGraph native `/threads` `/runs` API |

---

## 11. Implementation Phases

### Phase 1: Foundation + Core Agent (MVP)

- Project scaffolding + `langgraph.json` configuration
- PostgreSQL (Docker Compose) + business table migrations
- Auth multi-tenant authentication
- Agent Graph Factory (dynamic per-request construction)
- Skill system (system-level + tenant-level, with approval workflow)
- Console chat (frontend direct对接 LangGraph native API)
- Unit and integration tests (TDD approach)

### Phase 2: Channel + DingTalk Integration

- BaseChannel abstraction layer
- DingTalkChannel implementation
- DingTalk webhook receiver endpoint
- End-to-end: DingTalk message → Agent → DingTalk reply
- Channel configuration management page

### Phase 3: MCP + Cron + Polish

- MCP server management + dynamic tool loading
- Cron scheduled tasks (LangGraph native + webhook callback)
- Cron → DingTalk proactive push
- Management UI refinement (approval workflow UI, cron management UI)

### Phase 4: Production Hardening

- Logging / monitoring / alerting
- Performance optimization (graph factory caching, DB query optimization)
- Security hardening
- Deployment (Docker Compose)

---

## 12. Project Structure

```
project-root/
├── langgraph.json              # LangGraph Server configuration
├── .env                        # Environment variables (DATABASE_URI, etc.)
├── docker-compose.yml          # PostgreSQL + LangGraph Server
├── pyproject.toml              # Python dependencies
├── src/
│   ├── agent/
│   │   ├── graph.py            # make_graph() factory
│   │   ├── skills.py           # Skill → Tool conversion
│   │   ├── tools.py            # Built-in tools
│   │   └── mcp.py              # MCP tool loading
│   ├── auth.py                 # Multi-tenant auth
│   ├── checkpointer.py         # PostgresSaver factory
│   ├── custom_app.py           # FastAPI custom routes
│   ├── channels/
│   │   ├── base.py             # BaseChannel
│   │   ├── dingtalk.py         # DingTalkChannel
│   │   ├── console.py          # ConsoleChannel
│   │   └── manager.py          # ChannelManager
│   ├── cron/
│   │   └── callback.py         # Webhook callback handler
│   ├── db/
│   │   ├── migrations/         # SQL migration scripts
│   │   └── client.py           # Database client
│   └── models/                 # Pydantic models
├── console/                    # Forked QwenPaw Console (React/TS)
│   └── src/
│       ├── pages/
│       ├── api/
│       ├── stores/
│       └── components/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## 13. Testing Strategy

TDD approach: write tests before implementation code.

### Test Categories

| Category | Scope | Tools |
|----------|-------|-------|
| Unit | Individual functions, models, parsers | pytest, unittest.mock |
| Integration | DB operations, API endpoints, auth flow | pytest + testcontainers (PG) |
| Contract | Channel interface compliance | pytest |
| E2E | Full message flow: webhook → agent → response | pytest + httpx |

### Key Test Scenarios

- Graph factory produces correct tools for different tenant configs
- Skill approval workflow state transitions (draft→pending→approved/rejected)
- Auth correctly filters resources by tenant_id
- DingTalk webhook parsing extracts correct user_id and content
- Cron webhook callback routes response to correct channel
- Thread ID encoding/decoding roundtrip
- MCP tool loading from different transports
