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

### 3.3 Health 端点简化

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

## 7. 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|----------|------|
| 新建 | `openagentic_sdk/server/cluster_chat_host_daily.py` | 精简版 Host |
| 新建 | `openagentic_sdk/server/worker_registry.py` | Worker 注册模块 |
| 新建 | `deploy/docker/Dockerfile.daily` | 日常版 Dockerfile |
| 新建 | `deploy/docker/docker-compose.daily.yml` | 日常版 compose |
| 新建 | `deploy/docker/openagentic.daily.json` | 日常版配置 |
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
