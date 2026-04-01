# Daily Assistant 设计文档

> **版本**: v1.0
> **日期**: 2026-04-01
> **分支**: `daily-assistant`

## 1. 概述

### 1.1 背景

当前 `exp/v56-k3s-remote-subagent-spike` 分支针对**代码开发场景**设计，具有以下特点：
- Git 强一致性同步
- 代码仓库只读挂载
- 远程 K3s Worker 执行代码分析任务

### 1.2 目标

创建 **Daily Assistant** 分支，针对**日常工作场景**：
- 无 Git 同步要求
- 无代码仓库挂载
- 保留远程 Worker 支持
- 专业化 Agent（翻译、写作、研究等）

### 1.3 使用场景

| 场景 | 描述 |
|------|------|
| 日常对话 | 问答、咨询、头脑风暴 |
| 文档写作 | 文章润色、邮件撰写、报告生成 |
| 多语言翻译 | 中英互译、专业术语翻译 |
| 信息研究 | 网络搜索、资料整理、分析总结 |

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Web Browser                           │
│                    (http://localhost:3001)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Nginx (Web Server)                      │
│              静态文件 + API 代理 + SSE 代理                   │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│     Host        │ │  Worker-Trans   │ │  Worker-Writer  │
│  (调度中心)      │ │   (翻译 Agent)   │ │   (写作 Agent)   │
│                 │ │                 │ │                 │
│ - HTTP API      │ │ - Agent 执行    │ │ - Agent 执行    │
│ - SSE 广播      │ │ - 动态注册      │ │ - 动态注册      │
│ - Worker 管理   │ │ - 心跳上报      │ │ - 心跳上报      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 2.2 与开发版本对比

| 组件 | 开发版本 (exp/v56) | 日常版本 (daily) |
|------|-------------------|------------------|
| Git 同步 | ✅ CommittedGitSynchronizer | ❌ 移除 |
| 代码挂载 | ✅ /workspace/repo:ro | ❌ 移除 |
| 远程 Worker | ✅ K3s 集群 | ✅ Docker 容器 |
| Agent 类型 | research, code-review | translator, writer, researcher |
| Session 存储 | /tmp/sessions | ~/.openagentic/sessions |
| Worker 发现 | 配置文件 | 动态注册 + 心跳 |

## 3. 核心组件设计

### 3.1 cluster_chat_host_daily.py

从 `cluster_chat_host.py` 精简，移除以下功能：
- `GitSyncResult` 数据类
- `CommittedGitSynchronizer` 导入和使用
- `_sync_result_for_session()` 函数
- Session 元数据中的 git_revision, authoritative_revision
- `--sync-mirror` 参数

保留核心功能：
- HTTP Server（health, event, session API）
- SSE 事件广播
- 远程 Worker 调度
- Agent 路由
- Session 持久化

### 3.2 Worker 动态注册机制

#### 3.2.1 注册流程

```
Worker 启动
    │
    ▼
POST /worker/register ──→ Host 记录 Worker 信息
    │                         │
    │                         ▼
    │                    广播 worker.registered 事件到 SSE
    │
    ▼
定时心跳 (30s) ──→ POST /worker/heartbeat ──→ 更新 last_heartbeat
                                              │
                                              ▼
                                    超过 90s 无心跳 → 标记 offline
```

#### 3.2.2 API 定义

**POST /worker/register**

Request:
```json
{
  "node_name": "worker-translate",
  "agents": [
    {
      "name": "translator-zh-en",
      "description": "中英翻译专家",
      "model": "gpt-5.4",
      "tools": ["Read", "Write"]
    }
  ]
}
```

Response:
```json
{
  "ok": true,
  "session_timeout_s": 90
}
```

**POST /worker/unregister**

Request:
```json
{
  "node_name": "worker-translate"
}
```

Response:
```json
{
  "ok": true
}
```

**POST /worker/heartbeat**

Request:
```json
{
  "node_name": "worker-translate"
}
```

Response:
```json
{
  "ok": true
}
```

#### 3.2.3 内存数据结构

```python
@dataclass
class WorkerInfo:
    node_name: str
    agents: list[AgentConfig]
    last_heartbeat: float
    status: Literal["online", "offline"]

# 运行时注册表
registered_workers: dict[str, WorkerInfo] = {}
```

#### 3.2.4 Agent 合并逻辑

```python
def get_available_agents() -> dict[str, list[AgentConfig]]:
    # 1. 静态配置（daily.json）
    static_agents = load_static_agents_from_config()

    # 2. 动态注册的 Worker
    dynamic_workers = {
        name: info.agents
        for name, info in registered_workers.items()
        if info.status == "online"
    }

    # 3. 合并：动态注册覆盖静态配置中的同名 Agent
    return merge_agent_configs(static_agents, dynamic_workers)
```

#### 3.2.5 Agent 路由逻辑

当 Host 收到用户消息需要分发到 Agent 时，需要确定目标 Worker：

```python
# 路由数据结构
agent_to_worker: dict[str, str] = {}  # agent_name -> node_name
worker_urls: dict[str, str] = {}      # node_name -> base_url

def register_worker(node_name: str, base_url: str, agents: list[AgentConfig]):
    worker_urls[node_name] = base_url
    for agent in agents:
        agent_to_worker[agent.name] = node_name

def get_worker_url_for_agent(agent_name: str) -> str | None:
    node_name = agent_to_worker.get(agent_name)
    if node_name:
        return worker_urls.get(node_name)
    return None

# 分发逻辑
async def dispatch_to_agent(agent_name: str, prompt: str, session_id: str):
    worker_url = get_worker_url_for_agent(agent_name)
    if not worker_url:
        raise AgentNotFoundError(f"No worker registered for agent: {agent_name}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{worker_url}/task",
            json={"agent": agent_name, "prompt": prompt, "session_id": session_id}
        )
        return response.json()
```

### 3.3 Worker 端注册客户端

#### 3.3.1 worker_register_client.py

```python
"""Worker 注册客户端 - 负责向 Host 注册并维持心跳"""
import asyncio
import httpx
from dataclasses import dataclass

@dataclass
class WorkerConfig:
    node_name: str
    base_url: str
    register_url: str
    agents: list[dict]
    heartbeat_interval_s: float = 30.0

class WorkerRegisterClient:
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.client = httpx.AsyncClient()
        self.running = False

    async def register(self) -> bool:
        """向 Host 注册 Worker"""
        try:
            response = await self.client.post(
                self.config.register_url,
                json={
                    "node_name": self.config.node_name,
                    "base_url": self.config.base_url,
                    "agents": self.config.agents,
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                print(f"[Worker] Registered successfully: {self.config.node_name}")
                return True
            else:
                print(f"[Worker] Registration failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"[Worker] Registration error: {e}")
            return False

    async def heartbeat(self) -> bool:
        """发送心跳"""
        try:
            response = await self.client.post(
                f"{self.config.register_url.rsplit('/', 1)[0]}/heartbeat",
                json={"node_name": self.config.node_name},
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"[Worker] Heartbeat error: {e}")
            return False

    async def unregister(self):
        """取消注册"""
        try:
            await self.client.post(
                f"{self.config.register_url.rsplit('/', 1)[0]}/unregister",
                json={"node_name": self.config.node_name},
                timeout=5.0,
            )
        except Exception:
            pass

    async def run_forever(self):
        """注册并持续发送心跳"""
        # 首次注册（带重试）
        for attempt in range(5):
            if await self.register():
                break
            await asyncio.sleep(2 ** attempt)  # 指数退避
        else:
            raise RuntimeError("Failed to register after 5 attempts")

        self.running = True
        try:
            while self.running:
                await asyncio.sleep(self.config.heartbeat_interval_s)
                await self.heartbeat()
        finally:
            await self.unregister()
```

#### 3.3.2 错误处理

```python
# Worker 行为
# - 注册失败：指数退避重试，最多 5 次，然后退出
# - 心跳失败：继续运行，下次心跳再试
# - 收到 SIGTERM：先 unregister 再退出

# Host 行为
# - 重复 node_name 注册：覆盖旧记录，日志警告
# - 心跳超时 (>90s)：标记 offline，保留记录 5 分钟后删除
```

### 3.4 Health 端点简化

**Response 示例**:
```json
{
  "ok": true,
  "deployment_mode": "daily-assistant",
  "provider_ready": true,
  "provider_profiles": ["anthropic", "openai"],
  "workers": {
    "translator-zh-en": [
      {
        "name": "translator",
        "description": "中英翻译专家",
        "model": "gpt-5.4",
        "tools": []
      }
    ],
    "writer-assistant": [
      {
        "name": "writer",
        "description": "写作助手",
        "model": "claude-sonnet-4-6",
        "tools": []
      }
    ]
  }
}
```

移除字段：`git_revision`, `cwd`, `config_source`

## 4. 配置文件设计

### 4.1 openagentic.daily.json

```json
{
  "$schema": "https://raw.githubusercontent.com/lemonhall/openagentic-sdk/main/openagentic.daily.schema.json",
  "providers": {
    "anthropic": {
      "kind": "anthropic",
      "api_key_env": "ANTHROPIC_API_KEY"
    },
    "openai": {
      "kind": "openai_compatible",
      "base_url_env": "OPENAI_BASE_URL",
      "api_key_env": "OPENAI_API_KEY",
      "default_model": "gpt-4o"
    }
  },
  "host": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6"
  },
  "agents": {
    "translator": {
      "description": "翻译专家 - 支持多语言互译",
      "prompt": "你是一个专业翻译。准确、流畅、地道地翻译用户提供的文本。保持原文风格，适当本地化。",
      "tools": [],
      "provider": "anthropic",
      "model": "claude-sonnet-4-6"
    },
    "writer": {
      "description": "写作助手 - 文章润色、创意写作",
      "prompt": "你是一个写作专家。帮助用户润色文章、提供创意写作建议、改进表达方式。",
      "tools": [],
      "provider": "anthropic",
      "model": "claude-sonnet-4-6"
    },
    "researcher": {
      "description": "研究助手 - 信息搜集、分析总结",
      "prompt": "你是一个研究助手。帮助用户搜集信息、分析问题、总结要点。使用搜索工具获取最新信息。",
      "tools": ["WebSearch", "WebFetch"],
      "provider": "anthropic",
      "model": "claude-sonnet-4-6"
    }
  }
}
```

### 4.2 配置变化说明

| 字段 | 开发版本 | 日常版本 |
|------|---------|---------|
| `executor.kind` | k3s | 移除（动态注册） |
| `executor.node_name` | worker-0 | 移除 |
| `workspace.mode` | readonly | 移除 |
| `worker.*` | 有 | 移除 |
| Agent 类型 | research, code-review | translator, writer, researcher |

## 5. 部署配置

### 5.1 docker-compose.daily.yml

```yaml
# docker-compose.daily.yml - Daily Assistant 部署
services:
  host:
    build:
      context: ../..
      dockerfile: deploy/docker/Dockerfile.daily
    image: oa-daily:latest
    container_name: oa-daily-host
    ports:
      - "${HOST_PORT:-8766}:8766"
    volumes:
      - oa-sessions:/home/user/.openagentic/sessions
    environment:
      - PYTHONUNBUFFERED=1
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL:-}
    command: >
      --host 0.0.0.0
      --port 8766
      --config /app/config/openagentic.daily.json
      --session-root /home/user/.openagentic/sessions
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8766/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker-translate:
    build:
      context: ../..
      dockerfile: deploy/docker/Dockerfile.worker
    image: oa-worker:latest
    container_name: oa-worker-translate
    environment:
      - AGENT_NAME=translator
      - AGENT_DESCRIPTION=翻译专家 - 支持多语言互译
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    command: >
      --port 8765
      --register-url http://host:8766/worker/register
      --agent-name translator
    depends_on:
      host:
        condition: service_healthy

  worker-writer:
    build:
      context: ../..
      dockerfile: deploy/docker/Dockerfile.worker
    image: oa-worker:latest
    container_name: oa-worker-writer
    environment:
      - AGENT_NAME=writer
      - AGENT_DESCRIPTION=写作助手 - 文章润色、创意写作
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    command: >
      --port 8765
      --register-url http://host:8766/worker/register
      --agent-name writer
    depends_on:
      host:
        condition: service_healthy

  web:
    image: nginx:alpine
    container_name: oa-daily-web
    ports:
      - "${WEB_PORT:-3001}:80"
    volumes:
      - ./web/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - host
    restart: unless-stopped

volumes:
  oa-sessions:
```

### 5.2 Dockerfile.daily

```dockerfile
# Dockerfile.daily - Daily Assistant Host (精简版)
FROM python:3.12-slim

WORKDIR /app

# 安装最小依赖（无 git）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制并安装 SDK
COPY pyproject.toml ./
COPY openagentic_sdk ./openagentic_sdk
RUN pip install --no-cache-dir -e .

# 复制配置
COPY deploy/docker/openagentic.daily.json /app/config/

# 创建 session 目录
RUN mkdir -p /home/user/.openagentic/sessions

EXPOSE 8766

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8766/health || exit 1

ENTRYPOINT ["python", "-u", "-m", "openagentic_sdk.server.cluster_chat_host_daily"]
CMD ["--host", "0.0.0.0", "--port", "8766"]
```

## 6. Web UI 适配

Web UI 代码完全复用，只需确保：
- Worker 标签页正确显示动态注册的 Agent
- Session 列表从新路径加载

无需修改前端代码。

### 6.1 Web UI 构建

Web UI 源码位于 `deploy/docker/web/`，构建步骤：

```bash
cd deploy/docker/web
npm install
npm run build
# 产物生成到 deploy/docker/web/dist/
```

docker-compose.daily.yml 中的 web 服务直接挂载构建产物。

### 6.2 nginx.conf

```nginx
# nginx.conf - Daily Assistant Web UI 代理
server {
    listen 80;

    # 静态文件
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # API 代理到 Host
    location /session {
        proxy_pass http://host:8766;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE 事件流
    location /event {
        proxy_pass http://host:8766;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }

    # Health 检查
    location /health {
        proxy_pass http://host:8766;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

## 7. 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| 新建 | `openagentic_sdk/server/cluster_chat_host_daily.py` | 精简版 Host（无 Git 同步） |
| 新建 | `openagentic_sdk/server/worker_registry.py` | Host 端 Worker 注册管理 |
| 新建 | `openagentic_sdk/server/worker_register_client.py` | Worker 端注册客户端 |
| 新建 | `deploy/docker/Dockerfile.daily` | 日常版 Host Dockerfile |
| 新建 | `deploy/docker/docker-compose.daily.yml` | 日常版 compose |
| 新建 | `deploy/docker/openagentic.daily.json` | 日常版配置文件 |
| 新建 | `deploy/docker/nginx.daily.conf` | 日常版 nginx 配置 |
| 复用 | `deploy/docker/web/*` | Web UI 无改动 |
| 复用 | `deploy/docker/Dockerfile.worker` | Worker 镜像复用 |

## 8. 测试计划

1. **启动测试**
   ```bash
   docker compose -f docker-compose.daily.yml up -d
   curl http://localhost:8766/health
   ```

2. **Worker 注册测试**
   ```bash
   # 检查 Worker 是否注册成功
   curl http://localhost:8766/health | jq '.workers'
   ```

3. **Web UI 测试**
   - 访问 http://localhost:3001
   - 验证 Worker 标签页显示 translator, writer
   - 发送消息测试对话流程

4. **Session 持久化测试**
   - 创建对话
   - 重启容器
   - 验证对话历史保留

## 9. 后续扩展

- [ ] 支持更多预置 Agent（如 calendar, email）
- [ ] Worker 能力协商（动态发现 Agent 支持的 tools）
- [ ] 负载均衡（多个同类 Worker 分发）
- [ ] Web UI 添加 Agent 选择器
