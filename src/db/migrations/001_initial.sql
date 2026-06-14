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
