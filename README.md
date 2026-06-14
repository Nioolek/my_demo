# 多租户店铺管理 AI Agent 平台

基于 LangGraph 的多租户 AI Agent 平台，为零售店铺管理者提供智能助手服务，支持钉钉集成、MCP 工具扩展、定时任务推送。

## 项目架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (React/Vite)                          │
│                     http://localhost:5173                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ API Proxy
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Server (Python)                     │
│                     http://localhost:2024                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Custom App │  │  Agent API  │  │  Threads    │              │
│  │  /api/*     │  │  /runs      │  │  /threads   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Webhooks   │  │  MCP Tools  │  │  Cron Jobs  │              │
│  │  /webhooks  │  │  load_mcp   │  │  crons API  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL 16                               │
│                       localhost:5432                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   tenants   │  │    users    │  │   agents    │              │
│  │  channels   │  │ mcp_servers │  │ cron_jobs   │              │
│  │ skills_meta │  │  threads    │  │ checkpoint  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## 功能特性

- ✅ **多租户架构**：每个店铺独立租户，数据隔离
- ✅ **钉钉集成**：Webhook 接收消息，自动创建用户，Session 回复
- ✅ **MCP 工具扩展**：动态加载 MCP 服务器工具 (SSE/stdio)
- ✅ **Skills 技能系统**：可审批的技能管理，支持租户/系统级别
- ✅ **定时任务**：LangGraph 原生 Cron，完成后主动推送钉钉
- ✅ **JWT 认证**：多租户身份验证，资源级权限控制
- ✅ **结构化日志**：生产环境 JSON 格式，便于聚合分析
- ✅ **速率限制**：防止 API 滥用

---

## 快速启动

### 1. 环境要求

- Python 3.13+
- Node.js 18+ (前端)
- PostgreSQL 16
- Docker & Docker Compose (可选)

### 2. 安装依赖

**后端：**

```bash
# 克隆项目
git clone https://github.com/Nioolek/my_demo.git
cd my_demo

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 激活虚拟环境 (Linux/Mac)
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"
```

**前端：**

```bash
cd CoPaw_fork/console

# 安装依赖
npm install

# 返回项目根目录
cd ../..
```

### 3. 配置环境变量

复制 `.env.example` 并修改：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# PostgreSQL 数据库
DATABASE_URI=postgresql://storeagent:storeagent@localhost:5432/storeagent

# JWT 认证（生产环境务必更换为 32+ 字符密钥）
JWT_SECRET=change-me-in-production-use-32-bytes-minimum
JWT_ALGORITHM=HS256

# LLM API（使用火山引擎或 OpenAI）
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
OPENAI_API_MODEL=gpt-4o

# 应用环境
APP_ENV=development
LOG_LEVEL=INFO
```

### 4. 启动数据库

**使用 Docker Compose：**

```bash
docker compose up -d postgres
```

**或本地 PostgreSQL：**

确保 PostgreSQL 运行，并创建数据库：

```sql
CREATE DATABASE storeagent;
CREATE USER storeagent WITH PASSWORD 'storeagent';
GRANT ALL PRIVILEGES ON DATABASE storeagent TO storeagent;
```

### 5. 运行数据库迁移

```bash
# Windows
.venv\Scripts\python -m src.db.migrations.runner

# Linux/Mac
.venv/Scripts/python -m src.db.migrations.runner
```

### 6. 启动后端服务

```bash
# Windows
.venv\Scripts\langgraph dev

# Linux/Mac
.venv/bin/langgraph dev
```

后端地址：`http://localhost:2024`

API 文档：`http://localhost:2024/docs`

### 7. 启动前端服务

```bash
cd CoPaw_fork/console
npm run dev
```

前端地址：`http://localhost:5173`

---

## 完整启动脚本

**Windows (`start.bat`)：**

```batch
@echo off
echo === 启动数据库 ===
docker compose up -d postgres

echo === 等待 PostgreSQL 就绪 ===
timeout /t 5 /nobreak

echo === 运行迁移 ===
.venv\Scripts\python -m src.db.migrations.runner

echo === 启动后端 ===
start "LangGraph Server" cmd /k .venv\Scripts\langgraph dev

echo === 启动前端 ===
cd CoPaw_fork\console
start "Frontend" cmd /k npm run dev

echo === 完成 ===
echo 后端: http://localhost:2024
echo 前端: http://localhost:5173
pause
```

**Linux/Mac (`start.sh`)：**

```bash
#!/bin/bash
echo "=== 启动数据库 ==="
docker compose up -d postgres

echo "=== 等待 PostgreSQL 就绪 ==="
sleep 5

echo "=== 运行迁移 ==="
.venv/bin/python -m src.db.migrations.runner

echo "=== 启动后端 ==="
.venv/bin/langgraph dev &

echo "=== 启动前端 ==="
cd CoPaw_fork/console && npm run dev &

echo "=== 完成 ==="
echo "后端: http://localhost:2024"
echo "前端: http://localhost:5173"
```

---

## 使用指南

### 创建租户和用户

**通过 API：**

```bash
# 创建租户
curl -X POST http://localhost:2024/api/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "我的店铺"}'

# 响应包含 tenant_id，用于后续操作
```

**通过数据库：**

```sql
INSERT INTO tenants (id, name) VALUES (gen_random_uuid(), '我的店铺');
INSERT INTO users (id, tenant_id, name, role, channel_source)
VALUES ('user-001', '<tenant_id>', '店长', 'manager', 'console');
```

### 获取 JWT Token

```bash
# 登录获取 token
curl -X POST http://localhost:2024/api/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001", "tenant_id": "<tenant_id>"}'

# 或通过 Python
python -c "
from src.auth import create_token
print(create_token('user-001', '<tenant_id>'))
"
```

### 配置钉钉机器人

1. 在钉钉群添加自定义机器人
2. 获取 `appKey` 和 `appSecret`
3. 配置 Webhook 回调地址

```bash
TOKEN="<your-jwt-token>"

# 创建 DingTalk Channel
curl -X POST http://localhost:2024/api/channels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_type": "dingtalk",
    "config": {
      "app_key": "<钉钉AppKey>",
      "app_secret": "<钉钉AppSecret>"
    }
  }'

# 设置钉钉机器人回调地址
# http://your-server:2024/webhooks/dingtalk
```

用户在钉钉群发消息 → 机器人自动回复，新用户自动创建账号。

### 与 Agent 对话

**API 方式：**

```bash
TOKEN="<your-jwt-token>"
TENANT_ID="<your-tenant-id>"

# 创建会话线程
THREAD=$(curl -s -X POST http://localhost:2024/threads \
  -H "Authorization: Bearer $TOKEN" | jq -r '.thread_id')

# 发送消息并等待回复
curl -X POST "http://localhost:2024/threads/$THREAD/runs/wait" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "store-agent",
    "input": {"messages": [{"role": "user", "content": "帮我检查今天的订单"}]},
    "config": {"configurable": {"tenant_id": "'$TENANT_ID'"}}
  }' | jq '.messages[-1].content'
```

**Python 方式：**

```python
import asyncio
from src.auth import create_token
from src.agent.graph import make_graph
from src.db.client import get_pool, close_pool
from langchain_core.messages import HumanMessage

async def chat():
    await get_pool()

    tenant_id = "<your-tenant-id>"
    config = {"configurable": {"tenant_id": tenant_id}}

    graph = await make_graph(config, None)
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="现在几点了？")]},
        config=config,
    )

    for msg in result["messages"]:
        if msg.type == "ai":
            print(f"Agent: {msg.content}")

    await close_pool()

asyncio.run(chat())
```

### 配置定时任务

```bash
TOKEN="<your-jwt-token>"

# 创建每日提醒任务
curl -X POST http://localhost:2024/api/cron-jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "每日库存提醒",
    "schedule": "0 9 * * *",
    "description": "每天早上9点提醒检查库存",
    "input_template": {
      "messages": [{"role": "user", "content": "请检查今日库存状态"}]
    },
    "timezone": "Asia/Shanghai"
  }'
```

任务完成后自动推送到钉钉。

### 添加 MCP 工具服务器

```bash
TOKEN="<your-jwt-token>"

# SSE 方式（远程 MCP 服务器）
curl -X POST http://localhost:2024/api/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "weather-api",
    "transport": "sse",
    "url": "http://mcp-server:8080/sse"
  }'

# Stdio 方式（本地 MCP 服务器）
curl -X POST http://localhost:2024/api/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "local-tools",
    "transport": "stdio",
    "command": "python",
    "args": ["-m", "my_mcp_server"]
  }'
```

---

## Docker 生产部署

### 构建镜像

```bash
docker build -t store-agent-platform .
```

### 使用 Docker Compose

```bash
# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f langgraph

# 停止服务
docker compose down
```

服务地址：
- LangGraph API: `http://localhost:2024`
- PostgreSQL: `localhost:5432`

---

## API 端点一览

### Custom App API (`/api/*`)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/tenants` | GET/POST | 租户管理 |
| `/api/login` | POST | 用户登录 |
| `/api/skills` | GET/POST | Skills CRUD |
| `/api/skills/{id}/submit` | POST | 提交审批 |
| `/api/skills/{id}/approve` | POST | 审批通过 |
| `/api/agents` | GET/POST | Agent 配置 |
| `/api/channels` | GET/POST/PUT/DELETE | Channel 管理 |
| `/api/mcp` | GET/POST/PUT/DELETE | MCP 服务器管理 |
| `/api/cron-jobs` | GET/POST/PUT/DELETE | 定时任务管理 |
| `/api/cron-jobs/{id}/toggle` | POST | 启用/禁用任务 |

### LangGraph Native API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/threads` | GET/POST | 会话线程管理 |
| `/threads/{id}/runs` | POST | 创建 Run |
| `/threads/{id}/runs/wait` | POST | 等待 Run 完成 |
| `/threads/{id}/state` | GET | 获取线程状态 |
| `/assistants` | GET | Assistant 列表 |
| `/crons` | GET/POST/PUT/DELETE | LangGraph Cron |

### Webhook 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/webhooks/dingtalk` | POST | 钉钉机器人回调 |
| `/webhooks/internal/cron-callback` | POST | Cron 完成回调 |

---

## 测试

```bash
# 运行所有测试
.venv/Scripts/pytest tests/ -v

# 仅运行单元测试
.venv/Scripts/pytest tests/unit/ -v

# 仅运行集成测试
.venv/Scripts/pytest tests/integration/ -v

# 测试覆盖率
.venv/Scripts/pytest tests/ --cov=src --cov-report=html
```

---

## 项目结构

```
my_demo/
├── .env                    # 环境变量配置
├── .env.example            # 配置模板
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile              # 生产镜像构建
├── langgraph.json          # LangGraph Server 配置
├── pyproject.toml          # Python 项目配置
├── Makefile                # 常用命令
│
├── src/                    # 后端源码
│   ├── agent/              # Agent 核心逻辑
│   │   ├── graph.py        # 动态图工厂
│   │   ├── tools.py        # 工具加载
│   │   ├── skills.py       # Skill 转换
│   │   └── mcp_loader.py   # MCP 工具加载
│   │
│   ├── api/                # API 路由
│   │   ├── tenants.py      # 租户 API
│   │   ├── auth_routes.py  # 登录 API
│   │   ├── skills.py       # Skills API
│   │   ├── agents.py       # Agent 配置 API
│   │   ├── channels.py     # Channel API
│   │   ├── mcp.py          # MCP API
│   │   ├── cron_jobs.py    # Cron API
│   │   ├── webhooks.py     # 钉钉 Webhook
│   │   └── cron_callback.py# Cron 回调
│   │
│   ├── channels/           # 频道实现
│   │   ├── base.py         # BaseChannel ABC
│   │   ├── dingtalk.py     # 钉钉频道
│   │   └── manager.py      # ChannelManager
│   │
│   ├── db/                 # 数据库
│   │   ├── client.py       # 连接池
│   │   └── migrations/     # SQL 迁移
│   │
│   ├── models/             # Pydantic 模型
│   │   ├── tenant.py
│   │   ├── skill.py
│   │   ├── agent.py
│   │   ├── channel.py
│   │   ├── mcp.py
│   │   └── cron.py
│   │
│   ├── auth.py             # JWT 认证
│   ├── checkpointer.py     # PostgresSaver
│   ├── custom_app.py       # FastAPI 主应用
│   └── logging_config.py   # 结构化日志
│
├── tests/                  # 测试
│   ├── unit/               # 单元测试
│   └── integration/        # 集成测试
│
└── CoPaw_fork/             # 前端 (React)
    └── console/
        ├── src/            # React 源码
        ├── package.json    # 前端依赖
        └── vite.config.ts  # Vite 配置
```

---

## 常见问题

### 1. LangGraph dev 报 BlockingError

这是 `langgraph_runtime_inmem` 的已知限制，仅影响开发环境。生产环境使用 `langgraph-runtime-postgres` 或 LangGraph Cloud 无此问题。

**临时解决方案：** 直接用 Python 调用 Agent：

```python
from src.agent.graph import make_graph
graph = await make_graph(config, None)
result = await graph.ainvoke({"messages": [...]}, config=config)
```

### 2. 钉钉消息无响应

检查：
1. DingTalk Channel 是否创建且 enabled=true
2. 钉钉机器人 Webhook 地址是否正确配置
3. 查看日志是否有 `senderStaffId` 相关错误

### 3. MCP 工具加载失败

MCP 服务器需要实际运行。检查：
1. URL 是否可访问 (SSE)
2. Command 是否正确 (stdio)
3. 查看 `mcp_servers` 表中的 enabled 字段

### 4. JWT Token 无效

确保 `.env` 中 `JWT_SECRET` 与服务启动时加载的一致。重启服务后重新生成 Token。

---

## 技术栈

- **后端**: Python 3.13, LangGraph, FastAPI, Pydantic v2, psycopg3
- **前端**: React 18, Vite, Ant Design
- **数据库**: PostgreSQL 16
- **AI**: LangChain, langchain-mcp-adapters
- **部署**: Docker Compose

---

## License

MIT