# OpenAgentic SDK Docker 部署指南

## 目录结构

```
deploy/docker/
├── Dockerfile.host        # Host 镜像
├── Dockerfile.worker      # Worker 镜像
├── docker-compose.yml     # 容器编排 (Host + Worker)
├── .env.example           # 环境变量示例
├── openagentic.remote.json  # Agent 配置
└── README.md              # 本文档
```

## 快速开始

### 1. 配置环境变量

```bash
cd deploy/docker

# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入实际值
vim .env
```

### 2. 构建并启动

```bash
# 构建并启动所有服务 (Host + Worker)
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f

# 只启动 Worker
docker compose up -d worker

# 只启动 Host (需要 Worker 已运行)
docker compose up -d host
```

### 3. 验证

```bash
# 检查 Worker 健康状态
curl http://localhost:19000/health

# 检查 Host 健康状态
curl http://localhost:8766/health
```

预期输出:
```json
{"status": "ok", "ready": true}
```

## 单独构建镜像

```bash
# 构建 Worker 镜像
docker build -f Dockerfile.worker -t oa-worker:latest ../..

# 构建 Host 镜像
docker build -f Dockerfile.host -t oa-host:latest ../..
```

## 配置说明

### 环境变量

| 变量 | 必须 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 是 | Anthropic API Key |
| `HOST_PORT` | 否 | Host 映射端口，默认 8766 |
| `WORKER_NAME` | 是 | Worker 节点名称 |
| `WORKER_PORT` | 否 | Worker 映射端口，默认 19000 |
| `CODE_PATH` | 否 | 代码仓库路径，默认 ../.. |

### openagentic.remote.json

| 字段 | 说明 |
|------|------|
| `agents.*.executor.node_name` | Worker 节点标识，必须与 Host 端的 `--node-url` key 匹配 |
| `agents.*.workspace.mode` | `readonly` 只读 / `readwrite` 可写 |
| `agents.*.worker.max_concurrent_tasks` | 最大并发任务数 |
| `agents.*.worker.supervisor_policy` | 故障处理策略 |

## 多 Worker 部署

### 方式 1: docker-compose (单机)

```bash
# worker-0
WORKER_NAME=worker-0 WORKER_PORT=19000 docker compose up -d worker

# worker-1
WORKER_NAME=worker-1 WORKER_PORT=19001 docker compose up -d worker
```

### 方式 2: 多机部署

在每台机器上:

```bash
# 机器 1 (100.94.80.121)
ssh root@100.94.80.121
cd /opt/oa-worker
docker build -f Dockerfile.worker -t oa-worker .
docker run -d \
  --name oa-worker \
  -p 8765:8765 \
  -v /data/repo:/workspace/repo:ro \
  -e OA_REMOTE_NODE_NAME=worker-0 \
  -e ANTHROPIC_API_KEY=sk-xxx \
  oa-worker
```

然后在 Host 机器上启动 Host 连接远程 Worker:

```bash
docker run -d \
  --name oa-host \
  -p 8766:8766 \
  -v /data/repo:/workspace/repo:ro \
  -e ANTHROPIC_API_KEY=sk-xxx \
  oa-host \
  --host 0.0.0.0 \
  --port 8766 \
  --repo-root /workspace/repo \
  --session-root /tmp/sessions \
  --node-url worker-0=http://100.94.80.121:8765
```

## 架构说明

```
                    ┌─────────────────┐
                    │     Client      │
                    └────────┬────────┘
                             │ :8766
                    ┌────────▼────────┐
                    │      Host       │
                    │  (oa-host)      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼────────┐     │     ┌────────▼────────┐
     │     Worker-0    │     │     │     Worker-1    │
     │  (oa-worker)    │     │     │  (oa-worker)    │
     └─────────────────┘     │     └─────────────────┘
               :8765         │           :8765
```

- **Host**: 接收客户端请求，调度任务到 Worker
- **Worker**: 执行实际的 Agent 任务

## 故障排查

### 健康检查失败

```bash
# 查看容器日志
docker compose logs host
docker compose logs worker

# 手动检查
docker exec oa-host curl http://localhost:8766/health
docker exec oa-worker curl http://localhost:8765/health
```

### Host 无法连接 Worker

```bash
# 检查 Worker 是否健康
docker compose ps

# 检查网络连通性
docker exec oa-host curl http://worker:8765/health
```

### 内存不足

修改 `docker-compose.yml` 中的资源限制:

```yaml
deploy:
  resources:
    limits:
      memory: 4G
```
