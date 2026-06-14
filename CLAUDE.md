# Store Agent Platform - Multi-Tenant AI Agent for Retail

> **LangGraph Server-based multi-tenant AI agent platform with DingTalk integration, Skills approval workflow, MCP tools, and Cron scheduling.**

## Project Overview

This platform enables retail store managers to interact with an AI assistant via DingTalk (or console). Key features:

- **Multi-tenancy**: Each tenant (store) has isolated agents, skills, channels, MCP servers, and cron jobs
- **Dynamic Agent**: Graph factory loads tenant-specific model/prompt/skills/MCP tools per request
- **DingTalk Integration**: Webhook-based message flow with auto-provisioning and session reply
- **Skills Workflow**: SKILL.md format with draft → pending → approved/rejected approval flow
- **MCP Tools**: Connect external MCP servers (SSE/streamable_http/stdio) as agent tools
- **Cron Scheduling**: LangGraph native cron with webhook callback for proactive push

## Directory Structure

```
src/
├── agent/
│   ├── graph.py              # make_graph() factory (called per Run)
│   ├── tools.py              # Built-in tools + dynamic loading delegation
│   ├── skills.py             # SKILL.md parser + StructuredTool converter
│   └── mcp_loader.py         # MCP tool loading via langchain-mcp-adapters
├── api/
│   ├── tenants.py            # Tenant CRUD
│   ├── auth_routes.py        # Login endpoint
│   ├── skills.py             # Skill CRUD + approval workflow
│   ├── agents.py             # Agent config CRUD
│   ├── channels.py           # Channel CRUD
│   ├── mcp.py                # MCP server CRUD
│   ├── cron_jobs.py          # Cron CRUD + LangGraph sync + toggle
│   ├── webhooks.py           # DingTalk webhook + agent run pipeline
│   ├── cron_callback.py      # Cron completion webhook handler
│   └── deps.py               # get_current_user, get_tenant_id dependencies
├── channels/
│   ├── base.py               # BaseChannel ABC, IncomingMessage, thread_id utils
│   ├── dingtalk.py           # DingTalkChannel implementation
│   └── manager.py            # ChannelManager (outbound routing registry)
├── db/
│   ├── client.py             # Async PostgreSQL pool + execute/fetch helpers
│   └── migrations/
│       ├── 001_initial.sql   # All table DDL
│       └── runner.py         # Migration executor
├── models/                   # Pydantic models (tenant, skill, agent, channel, mcp, cron)
├── auth.py                   # JWT + LangGraph Auth integration
├── checkpointer.py           # AsyncPostgresSaver factory
├── custom_app.py             # FastAPI app (mounted into LangGraph Server)
├── logging_config.py         # Structured logging (structlog)
tests/
├── unit/                     # Model, parser, channel, manager tests
├── integration/              # API endpoint tests with DB
└── conftest.py               # Fixtures: async_client, tenant_with_user
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| **Auth** | | |
| POST | `/api/auth/login` | JWT token exchange |
| **Tenants** | | |
| GET | `/api/tenants` | List tenants |
| POST | `/api/tenants` | Create tenant |
| **Skills** | | |
| GET | `/api/skills` | List tenant's skills |
| POST | `/api/skills` | Create skill (draft) |
| GET | `/api/skills/pending` | List pending skills |
| POST | `/api/skills/{id}/submit` | Submit for approval |
| POST | `/api/skills/{id}/approve` | Approve skill |
| POST | `/api/skills/{id}/reject` | Reject skill |
| **Agents** | | |
| GET | `/api/agents` | List agents |
| POST | `/api/agents` | Create agent config |
| PUT | `/api/agents/{id}` | Update agent |
| **Channels** | | |
| GET | `/api/channels` | List channels |
| POST | `/api/channels` | Create channel (dingtalk) |
| PUT | `/api/channels/{id}` | Update channel |
| DELETE | `/api/channels/{id}` | Delete channel |
| **MCP** | | |
| GET | `/api/mcp` | List MCP servers |
| POST | `/api/mcp` | Add MCP server |
| PUT | `/api/mcp/{id}` | Update MCP config |
| DELETE | `/api/mcp/{id}` | Remove MCP server |
| **Cron** | | |
| GET | `/api/cron-jobs` | List cron jobs |
| POST | `/api/cron-jobs` | Create cron (syncs to LangGraph) |
| PUT | `/api/cron-jobs/{id}` | Update cron |
| DELETE | `/api/cron-jobs/{id}` | Delete cron |
| POST | `/api/cron-jobs/{id}/toggle` | Enable/disable |
| **Webhooks** | | |
| POST | `/webhooks/dingtalk` | DingTalk robot callback |
| POST | `/webhooks/internal/cron-callback` | LangGraph cron completion |

All `/api/*` endpoints require JWT auth (`Authorization: Bearer <token>`).

## Database Schema

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `tenants` | `id UUID`, `name`, `config JSONB` | Root entity |
| `users` | `id`, `tenant_id`, `name`, `role`, `channel_source` | Composite PK `(channel_source, id)` |
| `agents` | `tenant_id`, `model`, `system_prompt`, `temperature`, `config`, `enabled` | Tenant agent config |
| `skills_meta` | `tenant_id`, `name`, `scope`, `status`, `content`, `approved_by` | Draft→approved workflow |
| `channels` | `tenant_id`, `channel_type`, `config`, `enabled` | UNIQUE(tenant_id, channel_type) |
| `mcp_servers` | `tenant_id`, `name`, `transport`, `url`, `command`, `args`, `env` | SSE/streamable_http/stdio |
| `cron_jobs_meta` | `tenant_id`, `lg_cron_id`, `schedule`, `timezone`, `input_template` | Links to LangGraph cron |
| `threads_meta` | `thread_id`, `tenant_id`, `user_id`, `channel_type` | Thread metadata |

## Key Classes

| Class | Location | Purpose |
|-------|----------|---------|
| `BaseChannel` | `src/channels/base.py` | ABC: `channel`, `start()`, `stop()`, `send()`, `parse_incoming()` |
| `IncomingMessage` | `src/channels/base.py` | Dataclass: `user_id`, `tenant_id`, `content`, `session_id`, `channel`, `meta` |
| `DingTalkChannel` | `src/channels/dingtalk.py` | Implements webhook-based DingTalk integration |
| `ChannelManager` | `src/channels/manager.py` | Registry: `register()`, `get()`, `send()` |
| `Auth` | `src/auth.py` | LangGraph SDK auth with JWT extraction |

**Thread ID Format**: `{tenant_id}:{user_id}:{channel}:{session_id}`
- Built by `build_thread_id()`, parsed by `parse_thread_id()`

## Agent Graph Factory

`src/agent/graph.py:make_graph(config, runtime)` is called on every Run:

1. Extract `tenant_id` from `config.configurable`
2. Load agent config from DB (model, system_prompt, temperature)
3. Load built-in tools (`get_current_time`)
4. Load approved skills from `skills_meta` → convert to `StructuredTool`
5. Load MCP tools via `MultiServerMCPClient` (connects to enabled MCP servers)
6. Build `create_react_agent(model, tools, prompt)`
7. Return CompiledStateGraph

## DingTalk Message Flow

```
DingTalk Robot → POST /webhooks/dingtalk → 200 ACK
                                    → _process_dingtalk_message (async)
                                      → parse_incoming (DingTalkChannel)
                                      → _ensure_dingtalk_user (lookup or auto-provision)
                                      → _create_agent_run (LangGraph SDK wait)
                                      → _send_dingtalk_reply (session webhook)
```

**Auto-provision**: If user not in DB, finds tenant with `dingtalk` channel and creates user under that tenant.

## Cron Scheduling Flow

```
POST /api/cron-jobs → DB + LangGraph crons.create(webhook=callback_url)
LangGraph cron fires → Run executes
Run completes → POST /webhooks/internal/cron-callback
Callback → parse_thread_id → ChannelManager.send → DingTalk
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URI` | PostgreSQL connection string |
| `JWT_SECRET` | JWT signing key (32+ bytes for production) |
| `OPENAI_API_KEY` | LLM API key |
| `OPENAI_BASE_URL` | LLM API base URL (default: OpenAI) |
| `OPENAI_API_MODEL` | Model name (default: gpt-4o) |
| `APP_ENV` | `development` or `production` |
| `LOG_LEVEL` | `INFO`, `DEBUG`, etc. |

## Python Environment

- Use Python 3.13 virtual environment at `.venv/`
- Run: `.venv/Scripts/python`, `.venv/Scripts/pip`
- Tests: `.venv/Scripts/pytest tests/ -v`
- Dev server: `.venv/Scripts/langgraph dev --no-browser`

## Docker Deployment

```bash
docker compose up -d
# Services: postgres (5432), langgraph (2024)
```

## Testing

- **89 tests** (29 unit, 60 integration)
- All tests pass with `pytest tests/ -v`
- Integration tests require running PostgreSQL
- Fixtures in `tests/integration/conftest.py`: `async_client`, `tenant_with_user`

## LangGraph Configuration

`langgraph.json`:
- Graph: `store-agent` from `src/agent/graph.py:make_graph`
- HTTP app: `src/custom_app.py:app` (auth enabled)
- Auth: `src/auth.py:auth` (JWT-based)
- Checkpointer: PostgreSQL via `src/checkpointer.py:create_checkpointer`