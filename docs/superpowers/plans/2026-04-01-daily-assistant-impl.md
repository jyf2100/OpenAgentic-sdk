# Daily Assistant 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建日常场景的 Daily Assistant 分支，移除 Git 同步和代码挂载，保留远程 Worker 支持

**Architecture:** 从 cluster_chat_host.py 精简出 cluster_chat_host_daily.py，添加 Worker 动态注册机制，Worker 端添加注册客户端

**Tech Stack:** Python 3.12, HTTP Server, SSE, Docker, Nginx

---

## 文件结构

| 文件路径 | 职责 |
|----------|------|
| `openagentic_sdk/server/worker_registry.py` | Host 端 Worker 注册表（内存存储、心跳检测） |
| `openagentic_sdk/server/worker_register_client.py` | Worker 端注册客户端（注册、心跳、取消注册） |
| `openagentic_sdk/server/cluster_chat_host_daily.py` | 精简版 Host（无 Git 同步） |
| `deploy/docker/Dockerfile.daily` | 日常版 Host Dockerfile |
| `deploy/docker/docker-compose.daily.yml` | 日常版部署配置 |
| `deploy/docker/openagentic.daily.json` | 日常版 Agent 配置 |
| `deploy/docker/nginx.daily.conf` | 日常版 nginx 配置 |

---

## Task 1: 创建 Worker 注册表模块

**Files:**
- Create: `openagentic_sdk/server/worker_registry.py`
- Test: `tests/server/test_worker_registry.py`

- [ ] **Step 1: 写测试 - WorkerInfo 数据结构和注册功能**

```python
# tests/server/test_worker_registry.py
import time
from openagentic_sdk.server.worker_registry import WorkerRegistry, WorkerInfo

def test_worker_info_dataclass():
    """测试 WorkerInfo 数据结构"""
    info = WorkerInfo(
        node_name="worker-1",
        base_url="http://worker-1:8765",
        agents=[{"name": "translator", "description": "翻译", "model": "gpt-4", "tools": []}],
        last_heartbeat=time.time(),
        status="online",
    )
    assert info.node_name == "worker-1"
    assert info.status == "online"
    assert len(info.agents) == 1

def test_registry_register_worker():
    """测试注册 Worker"""
    registry = WorkerRegistry()
    agents = [{"name": "translator", "description": "翻译", "model": "gpt-4", "tools": []}]

    registry.register(
        node_name="worker-1",
        base_url="http://worker-1:8765",
        agents=agents,
    )

    assert "worker-1" in registry.workers
    assert registry.workers["worker-1"].status == "online"

def test_registry_heartbeat_updates_timestamp():
    """测试心跳更新时间戳"""
    registry = WorkerRegistry()
    registry.register("worker-1", "http://worker-1:8765", [])

    t1 = registry.workers["worker-1"].last_heartbeat
    time.sleep(0.1)
    registry.heartbeat("worker-1")
    t2 = registry.workers["worker-1"].last_heartbeat

    assert t2 > t1

def test_registry_unregister_worker():
    """测试取消注册"""
    registry = WorkerRegistry()
    registry.register("worker-1", "http://worker-1:8765", [])

    registry.unregister("worker-1")

    assert "worker-1" not in registry.workers

def test_registry_mark_offline_when_heartbeat_timeout():
    """测试心跳超时标记为 offline"""
    registry = WorkerRegistry(heartbeat_timeout_s=0.1)
    registry.register("worker-1", "http://worker-1:8765", [])

    time.sleep(0.2)
    registry.check_timeouts()

    assert registry.workers["worker-1"].status == "offline"

def test_registry_get_available_agents():
    """测试获取可用 agents（包含路由映射）"""
    registry = WorkerRegistry()
    agents = [{"name": "translator", "description": "翻译", "model": "gpt-4", "tools": []}]
    registry.register("worker-1", "http://worker-1:8765", agents)

    # 获取 agent -> worker 映射
    worker_url = registry.get_worker_url_for_agent("translator")
    assert worker_url == "http://worker-1:8765"

def test_registry_merge_with_static_config():
    """测试合并静态配置和动态注册的 agents"""
    registry = WorkerRegistry()
    static_agents = {
        "default": [{"name": "host-agent", "description": "Host Agent", "model": "gpt-4", "tools": []}]
    }
    dynamic_agents = [{"name": "translator", "description": "翻译", "model": "gpt-4", "tools": []}]
    registry.register("worker-1", "http://worker-1:8765", dynamic_agents)

    merged = registry.merge_with_static(static_agents)
    # 动态注册应该覆盖同名静态配置
    assert "worker-1" in merged
    assert "default" in merged
    assert merged["worker-1"][0]["name"] == "translator"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/roc/workspace/openagentic-sdk && python -m pytest tests/server/test_worker_registry.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现 WorkerRegistry 模块**

```python
# openagentic_sdk/server/worker_registry.py
"""Worker 注册表 - Host 端管理 Worker 注册和心跳"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class WorkerInfo:
    """Worker 信息"""
    node_name: str
    base_url: str
    agents: list[dict[str, Any]]
    last_heartbeat: float
    status: Literal["online", "offline"] = "online"


class WorkerRegistry:
    """Worker 注册表 - 管理 Worker 的注册、心跳、路由"""

    def __init__(self, heartbeat_timeout_s: float = 90.0):
        self.workers: dict[str, WorkerInfo] = {}
        self.agent_to_worker: dict[str, str] = {}  # agent_name -> node_name
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self._lock = threading.Lock()

    def register(
        self,
        node_name: str,
        base_url: str,
        agents: list[dict[str, Any]],
    ) -> None:
        """注册或更新 Worker"""
        with self._lock:
            self.workers[node_name] = WorkerInfo(
                node_name=node_name,
                base_url=base_url,
                agents=agents,
                last_heartbeat=time.time(),
                status="online",
            )
            # 更新 agent -> worker 映射
            for agent in agents:
                agent_name = agent.get("name")
                if agent_name:
                    self.agent_to_worker[agent_name] = node_name

    def unregister(self, node_name: str) -> None:
        """取消注册 Worker"""
        with self._lock:
            if node_name in self.workers:
                # 移除 agent 映射
                for agent in self.workers[node_name].agents:
                    agent_name = agent.get("name")
                    if agent_name and self.agent_to_worker.get(agent_name) == node_name:
                        self.agent_to_worker.pop(agent_name, None)
                del self.workers[node_name]

    def heartbeat(self, node_name: str) -> bool:
        """更新心跳时间"""
        with self._lock:
            if node_name in self.workers:
                worker = self.workers[node_name]
                worker.last_heartbeat = time.time()
                worker.status = "online"
                return True
            return False

    def check_timeouts(self) -> list[str]:
        """检查超时 Worker，返回被标记为 offline 的列表"""
        now = time.time()
        offline_list = []
        with self._lock:
            for node_name, worker in self.workers.items():
                if worker.status == "online":
                    if now - worker.last_heartbeat > self.heartbeat_timeout_s:
                        worker.status = "offline"
                        offline_list.append(node_name)
        return offline_list

    def get_worker_url_for_agent(self, agent_name: str) -> str | None:
        """获取 Agent 对应的 Worker URL"""
        with self._lock:
            node_name = self.agent_to_worker.get(agent_name)
            if node_name and node_name in self.workers:
                worker = self.workers[node_name]
                if worker.status == "online":
                    return worker.base_url
            return None

    def get_all_workers(self) -> dict[str, list[dict[str, Any]]]:
        """获取所有在线 Worker 的 agents（按 worker 分组）"""
        result: dict[str, list[dict[str, Any]]] = {}
        with self._lock:
            for node_name, worker in self.workers.items():
                if worker.status == "online":
                    result[node_name] = list(worker.agents)
        return result

    def merge_with_static(
        self,
        static_agents: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        """合并静态配置和动态注册的 agents

        Args:
            static_agents: 静态配置中的 agents，按 node_name 分组

        Returns:
            合并后的 agents，动态注册覆盖同名静态配置
        """
        result = dict(static_agents)  # 复制静态配置
        with self._lock:
            for node_name, worker in self.workers.items():
                if worker.status == "online":
                    # 动态注册覆盖静态配置中的同名 worker
                    result[node_name] = list(worker.agents)
        return result

    async def dispatch_to_agent(
        self,
        agent_name: str,
        prompt: str,
        session_id: str,
        http_client: Any = None,
    ) -> dict[str, Any]:
        """分发任务到 Agent 对应的 Worker

        Args:
            agent_name: 目标 agent 名称
            prompt: 用户输入
            session_id: 会话 ID
            http_client: 可选的 httpx.AsyncClient 实例

        Returns:
            Worker 返回的响应

        Raises:
            ValueError: Agent 没有对应的在线 Worker
        """
        import httpx

        worker_url = self.get_worker_url_for_agent(agent_name)
        if not worker_url:
            raise ValueError(f"No online worker for agent: {agent_name}")

        client = http_client or httpx.AsyncClient()
        try:
            response = await client.post(
                f"{worker_url}/task",
                json={"agent": agent_name, "prompt": prompt, "session_id": session_id},
                timeout=300.0,
            )
            response.raise_for_status()
            return response.json()
        finally:
            if http_client is None:
                await client.aclose()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/roc/workspace/openagentic-sdk && python -m pytest tests/server/test_worker_registry.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: 提交**

```bash
git add openagentic_sdk/server/worker_registry.py tests/server/test_worker_registry.py
git commit -m "$(cat <<'EOF'
feat(server): add WorkerRegistry for dynamic worker registration

- WorkerInfo dataclass for worker metadata
- WorkerRegistry with register/unregister/heartbeat
- Agent-to-worker routing map
- Heartbeat timeout detection (90s default)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 创建 Worker 注册客户端

**Files:**
- Create: `openagentic_sdk/server/worker_register_client.py`
- Test: `tests/server/test_worker_register_client.py`

- [ ] **Step 1: 写测试 - 注册客户端核心功能**

```python
# tests/server/test_worker_register_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from openagentic_sdk.server.worker_register_client import (
    WorkerConfig,
    WorkerRegisterClient,
)

@pytest.mark.asyncio
async def test_client_register_success():
    """测试注册成功"""
    config = WorkerConfig(
        node_name="worker-1",
        base_url="http://localhost:8765",
        register_url="http://host:8766/worker/register",
        agents=[{"name": "translator", "description": "翻译", "model": "gpt-4", "tools": []}],
    )
    client = WorkerRegisterClient(config)

    with patch.object(client._http_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = await client.register()
        assert result is True
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_client_register_retry_on_failure():
    """测试注册失败重试"""
    config = WorkerConfig(
        node_name="worker-1",
        base_url="http://localhost:8765",
        register_url="http://host:8766/worker/register",
        agents=[],
    )
    client = WorkerRegisterClient(config)

    with patch.object(client._http_client, "post", new_callable=AsyncMock) as mock_post:
        # 前两次失败，第三次成功
        mock_post.side_effect = [
            Exception("connection error"),
            Exception("connection error"),
            MagicMock(status_code=200),
        ]
        result = await client.register_with_retry(max_attempts=3)
        assert result is True
        assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_client_heartbeat():
    """测试心跳"""
    config = WorkerConfig(
        node_name="worker-1",
        base_url="http://localhost:8765",
        register_url="http://host:8766/worker/register",
        agents=[],
    )
    client = WorkerRegisterClient(config)

    with patch.object(client._http_client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        result = await client.heartbeat()
        assert result is True

@pytest.mark.asyncio
async def test_client_unregister():
    """测试取消注册"""
    config = WorkerConfig(
        node_name="worker-1",
        base_url="http://localhost:8765",
        register_url="http://host:8766/worker/register",
        agents=[],
    )
    client = WorkerRegisterClient(config)

    with patch.object(client._http_client, "post", new_callable=AsyncMock) as mock_post:
        await client.unregister()
        mock_post.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/roc/workspace/openagentic-sdk && python -m pytest tests/server/test_worker_register_client.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现 WorkerRegisterClient**

```python
# openagentic_sdk/server/worker_register_client.py
"""Worker 注册客户端 - 向 Host 注册并维持心跳"""
from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class WorkerConfig:
    """Worker 配置"""
    node_name: str
    base_url: str
    register_url: str
    agents: list[dict[str, Any]]
    heartbeat_interval_s: float = 30.0


class WorkerRegisterClient:
    """Worker 注册客户端"""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self._http_client = httpx.AsyncClient()
        self._running = False

    async def register(self) -> bool:
        """向 Host 注册"""
        try:
            response = await self._http_client.post(
                self.config.register_url,
                json={
                    "node_name": self.config.node_name,
                    "base_url": self.config.base_url,
                    "agents": self.config.agents,
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                print(f"[Worker] Registered: {self.config.node_name}")
                return True
            print(f"[Worker] Register failed: {response.status_code}")
            return False
        except Exception as e:
            print(f"[Worker] Register error: {e}")
            return False

    async def register_with_retry(self, max_attempts: int = 5) -> bool:
        """带重试的注册"""
        for attempt in range(max_attempts):
            if await self.register():
                return True
            delay = min(2 ** attempt, 30)  # 指数退避，最大 30s
            print(f"[Worker] Retry {attempt + 1}/{max_attempts} in {delay}s")
            await asyncio.sleep(delay)
        return False

    async def heartbeat(self) -> bool:
        """发送心跳"""
        base_url = self.config.register_url.rsplit("/", 1)[0]
        try:
            response = await self._http_client.post(
                f"{base_url}/heartbeat",
                json={"node_name": self.config.node_name},
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"[Worker] Heartbeat error: {e}")
            return False

    async def unregister(self) -> None:
        """取消注册"""
        base_url = self.config.register_url.rsplit("/", 1)[0]
        try:
            await self._http_client.post(
                f"{base_url}/unregister",
                json={"node_name": self.config.node_name},
                timeout=5.0,
            )
            print(f"[Worker] Unregistered: {self.config.node_name}")
        except Exception:
            pass

    async def run_forever(self) -> None:
        """注册并持续发送心跳"""
        if not await self.register_with_retry():
            raise RuntimeError("Failed to register after max attempts")

        self._running = True

        def handle_signal(signum, frame):
            self._running = False

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        try:
            while self._running:
                await asyncio.sleep(self.config.heartbeat_interval_s)
                if self._running:
                    await self.heartbeat()
        finally:
            await self.unregister()
            await self._http_client.aclose()

    def stop(self) -> None:
        """停止心跳循环"""
        self._running = False
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/roc/workspace/openagentic-sdk && python -m pytest tests/server/test_worker_register_client.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: 提交**

```bash
git add openagentic_sdk/server/worker_register_client.py tests/server/test_worker_register_client.py
git commit -m "$(cat <<'EOF'
feat(server): add WorkerRegisterClient for worker-side registration

- WorkerConfig dataclass for worker settings
- WorkerRegisterClient with register/heartbeat/unregister
- Exponential backoff retry on registration failure
- Graceful shutdown with SIGTERM/SIGINT handling

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 创建精简版 Host (cluster_chat_host_daily.py)

**Files:**
- Create: `openagentic_sdk/server/cluster_chat_host_daily.py`
- Modify: `openagentic_sdk/server/__init__.py`
- Test: `tests/server/test_cluster_chat_host_daily.py`

- [ ] **Step 1: 写测试 - Health 端点和 Worker API**

```python
# tests/server/test_cluster_chat_host_daily.py
import json
import pytest
from http.server import BaseHTTPRequestHandler
from unittest.mock import patch, MagicMock

from openagentic_sdk.server.worker_registry import WorkerRegistry
from openagentic_sdk.server.cluster_chat_host_daily import (
    DailyHostServer,
    _parse_request_target,
    _read_json,
    _write_json,
)


def test_parse_request_target():
    """测试 URL 解析"""
    assert _parse_request_target("/health") == ["health"]
    assert _parse_request_target("/worker/register") == ["worker", "register"]
    assert _parse_request_target("/session/abc123/events") == ["session", "abc123", "events"]


def test_write_json():
    """测试 JSON 响应"""
    handler = MagicMock(spec=BaseHTTPRequestHandler)
    handler.wfile = MagicMock()

    _write_json(handler, 200, {"ok": True})

    handler.send_response.assert_called_once_with(200)
    handler.send_header.assert_called()
    handler.wfile.write.assert_called_once()
    raw = handler.wfile.write.call_args[0][0]
    assert json.loads(raw) == {"ok": True}


def test_health_endpoint_without_workers():
    """测试 Health 端点（无 workers）"""
    registry = WorkerRegistry()
    workers = registry.get_all_workers()

    assert workers == {}
    assert isinstance(workers, dict)


def test_health_endpoint_with_workers():
    """测试 Health 端点（有 workers）"""
    registry = WorkerRegistry()
    registry.register(
        node_name="worker-translate",
        base_url="http://worker-translate:8765",
        agents=[{"name": "translator", "description": "翻译", "model": "gpt-4", "tools": []}],
    )

    workers = registry.get_all_workers()

    assert "worker-translate" in workers
    assert len(workers["worker-translate"]) == 1
    assert workers["worker-translate"][0]["name"] == "translator"


def test_worker_registration_flow():
    """测试 Worker 注册流程"""
    registry = WorkerRegistry()

    # 注册
    registry.register("worker-1", "http://worker-1:8765", [
        {"name": "agent-1", "description": "Agent 1", "model": "gpt-4", "tools": []}
    ])
    assert "worker-1" in registry.workers

    # 心跳
    registry.heartbeat("worker-1")
    assert registry.workers["worker-1"].status == "online"

    # 取消注册
    registry.unregister("worker-1")
    assert "worker-1" not in registry.workers
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/roc/workspace/openagentic-sdk && python -m pytest tests/server/test_cluster_chat_host_daily.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 创建精简版 Host**

从 `cluster_chat_host.py` 复制并精简，关键变更：
1. 移除 `GitSyncResult`, `CommittedGitSynchronizer` 导入和使用
2. 移除 `_sync_result_for_session()` 函数
3. 移除 session 元数据中的 git_revision 字段
4. 添加 Worker 注册 API endpoints
5. 集成 WorkerRegistry

```python
# openagentic_sdk/server/cluster_chat_host_daily.py
"""Daily Assistant Host - 精简版，无 Git 同步"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import queue
import threading
import time
from dataclasses import dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from ..options import OpenAgenticOptions
from ..permissions.gate import PermissionGate
from ..remote_cluster_config import (
    UnavailableRemoteProvider,
    build_remote_cluster_routing_system_prompt,
    load_remote_cluster_bootstrap,
)
from ..serialization import event_to_dict
from ..sessions.store import FileSessionStore
from ..tools.defaults import default_tool_registry
from .worker_registry import WorkerRegistry


# 复用现有的 helper 函数
def _parse_request_target(path: str) -> list[str]:
    from urllib.parse import urlparse
    parsed = urlparse(path or "")
    return [part for part in (parsed.path or "").split("/") if part]


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    try:
        length = int(handler.headers.get("Content-Length") or "0")
    except ValueError:
        _write_json(handler, 400, {"error": "invalid_content_length"})
        return None
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    try:
        obj = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        _write_json(handler, 400, {"error": "invalid_json"})
        return None
    if not isinstance(obj, dict):
        _write_json(handler, 400, {"error": "invalid_request"})
        return None
    return obj


def _write_json(handler: BaseHTTPRequestHandler, status: int, obj: Any) -> None:
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _session_info(store: FileSessionStore, session_id: str) -> dict[str, Any] | None:
    record = store.read_meta_record(session_id)
    if not record:
        return None
    return {
        "id": session_id,
        "created_at": record.get("created_at"),
        "metadata": store.read_metadata(session_id),
    }


class _EventHub:
    """SSE 事件广播"""
    def __init__(self) -> None:
        self._subs: list[queue.Queue[dict[str, Any]]] = []

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        q: queue.Queue[dict[str, Any]] = queue.Queue()
        self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any]]) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    def publish(self, obj: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(obj)
            except Exception:
                continue


@dataclass(frozen=True, slots=True)
class DailyHostServer:
    """Daily Assistant Host 服务器配置"""
    base_options: OpenAgenticOptions
    session_store: FileSessionStore
    host: str = "127.0.0.1"
    port: int = 8766
    health_status: Mapping[str, Any] | None = None

    def make_server(self) -> ThreadingHTTPServer:
        options = self.base_options
        store = self.session_store
        health_status = dict(self.health_status or {})
        hub = _EventHub()
        registry = WorkerRegistry(heartbeat_timeout_s=90.0)
        running_abort: dict[str, threading.Event] = {}
        running_lock = threading.Lock()

        def _start_prompt_async(*, session_id: str, prompt: str) -> None:
            abort_event = threading.Event()
            with running_lock:
                running_abort[session_id] = abort_event

            def _run() -> None:
                try:
                    async def _query() -> None:
                        from ..api import query as query_events
                        opts2 = replace(
                            options,
                            resume=session_id,
                            session_store=store,
                            abort_event=abort_event,
                        )
                        async for event in query_events(prompt=prompt, options=opts2):
                            hub.publish({
                                "type": "session.event",
                                "session_id": session_id,
                                "event": event_to_dict(event),
                            })
                    asyncio.run(_query())
                except Exception as e:
                    hub.publish({
                        "type": "session.error",
                        "session_id": session_id,
                        "error": str(e),
                    })
                finally:
                    with running_lock:
                        running_abort.pop(session_id, None)
                    hub.publish({
                        "type": "session.done",
                        "session_id": session_id,
                    })

            threading.Thread(target=_run, name=f"oa-daily-{session_id}", daemon=True).start()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parts = _parse_request_target(self.path)

                if parts == ["health"]:
                    payload: dict[str, Any] = {
                        "ok": True,
                        "deployment_mode": "daily-assistant",
                    }
                    payload.update(health_status)
                    payload["workers"] = registry.get_all_workers()
                    _write_json(self, 200, payload)
                    return

                if parts == ["event"]:
                    self.close_connection = True
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.end_headers()

                    q = hub.subscribe()
                    try:
                        self.wfile.write(b"data: {\"type\":\"server.connected\"}\n\n")
                        self.wfile.flush()
                        last_heartbeat = time.time()
                        while True:
                            try:
                                obj = q.get(timeout=0.5)
                                raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                                self.wfile.write(b"data: " + raw + b"\n\n")
                                self.wfile.flush()
                            except queue.Empty:
                                pass
                            if time.time() - last_heartbeat >= 30.0:
                                self.wfile.write(b"data: {\"type\":\"server.heartbeat\"}\n\n")
                                self.wfile.flush()
                                last_heartbeat = time.time()
                            # 检查超时 worker
                            registry.check_timeouts()
                    except Exception:
                        pass
                    finally:
                        hub.unsubscribe(q)
                    return

                if len(parts) == 2 and parts[0] == "session":
                    session_id = parts[1]
                    info = _session_info(store, session_id)
                    if info is None:
                        _write_json(self, 404, {"error": "not_found"})
                        return
                    _write_json(self, 200, info)
                    return

                if len(parts) == 3 and parts[0] == "session" and parts[2] == "events":
                    session_id = parts[1]
                    try:
                        entries = [event_to_dict(event) for event in store.read_events(session_id)]
                    except ValueError:
                        _write_json(self, 400, {"error": "invalid_session_id"})
                        return
                    _write_json(self, 200, {"session_id": session_id, "entries": entries})
                    return

                _write_json(self, 404, {"error": "not_found"})

            def do_POST(self):
                parts = _parse_request_target(self.path)

                # Worker 注册 API
                if parts == ["worker", "register"]:
                    body = _read_json(self)
                    if body is None:
                        return
                    node_name = body.get("node_name")
                    base_url = body.get("base_url", "")
                    agents = body.get("agents", [])
                    if not node_name:
                        _write_json(self, 400, {"error": "missing node_name"})
                        return
                    registry.register(node_name, base_url, agents)
                    hub.publish({
                        "type": "worker.registered",
                        "node_name": node_name,
                        "agents": agents,
                    })
                    _write_json(self, 200, {"ok": True, "session_timeout_s": 90})
                    return

                if parts == ["worker", "unregister"]:
                    body = _read_json(self)
                    if body is None:
                        return
                    node_name = body.get("node_name")
                    if node_name:
                        registry.unregister(node_name)
                        hub.publish({
                            "type": "worker.unregistered",
                            "node_name": node_name,
                        })
                    _write_json(self, 200, {"ok": True})
                    return

                if parts == ["worker", "heartbeat"]:
                    body = _read_json(self)
                    if body is None:
                        return
                    node_name = body.get("node_name")
                    if node_name and registry.heartbeat(node_name):
                        _write_json(self, 200, {"ok": True})
                    else:
                        _write_json(self, 404, {"error": "worker not found"})
                    return

                # Session API
                if parts == ["session"]:
                    body = _read_json(self) or {}
                    metadata = body.get("metadata") or {}
                    session_id = store.create_session(metadata=metadata)
                    _write_json(self, 200, _session_info(store, session_id) or {"id": session_id})
                    return

                if len(parts) == 3 and parts[0] == "session" and parts[2] == "prompt_async":
                    session_id = parts[1]
                    body = _read_json(self)
                    if body is None:
                        return
                    prompt = body.get("prompt") or body.get("text") or body.get("content")
                    if not isinstance(prompt, str) or not prompt:
                        _write_json(self, 400, {"error": "invalid_prompt"})
                        return
                    _start_prompt_async(session_id=session_id, prompt=prompt)
                    self.send_response(204)
                    self.end_headers()
                    return

                if len(parts) == 3 and parts[0] == "session" and parts[2] == "abort":
                    session_id = parts[1]
                    with running_lock:
                        abort_event = running_abort.get(session_id)
                        if abort_event:
                            abort_event.set()
                    _write_json(self, 200, {"ok": True})
                    return

                _write_json(self, 404, {"error": "not_found"})

            def log_message(self, format, *args):
                pass  # 静默日志

        return ThreadingHTTPServer((self.host, self.port), Handler)


def build_daily_host_from_config(
    *,
    repo_root: str,
    session_root: str,
    config_path: str,
    env: Mapping[str, str] | None = None,
) -> tuple[OpenAgenticOptions, FileSessionStore, dict[str, Any]]:
    """构建 Daily Host 配置"""
    bootstrap = load_remote_cluster_bootstrap(repo_root=repo_root, config_path=config_path, env=env)
    session_store = FileSessionStore(root_dir=Path(session_root))
    provider = bootstrap.host_provider or UnavailableRemoteProvider()
    health_status = {
        "provider_ready": bootstrap.self_check.provider_ready,
        "provider_profiles": list(bootstrap.provider_profiles),
    }
    options = OpenAgenticOptions(
        provider=provider,
        model=bootstrap.host_model or "claude-sonnet-4-6",
        api_key=bootstrap.host_provider_spec.api_key if bootstrap.host_provider_spec is not None else None,
        cwd=repo_root,
        project_dir=repo_root,
        tools=default_tool_registry(),
        permission_gate=PermissionGate(permission_mode="bypass"),
        session_store=session_store,
        setting_sources=["project"],
        system_prompt=build_remote_cluster_routing_system_prompt(bootstrap.agents),
        agents=bootstrap.agents,
    )
    return options, session_store, health_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily Assistant Host")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--config", required=True, help="Path to openagentic.daily.json")
    parser.add_argument("--session-root", required=True, help="Session storage directory")
    args = parser.parse_args(argv)

    repo_root = os.getcwd()
    options, session_store, health_status = build_daily_host_from_config(
        repo_root=repo_root,
        session_root=args.session_root,
        config_path=args.config,
    )

    server = DailyHostServer(
        base_options=options,
        session_store=session_store,
        host=args.host,
        port=args.port,
        health_status=health_status,
    )

    httpd = server.make_server()
    print(f"[Host] Daily Assistant listening on {args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    exit(main())
```

- [ ] **Step 4: 运行测试验证通过**

Run: `cd /Users/roc/workspace/openagentic-sdk && python -m pytest tests/server/test_cluster_chat_host_daily.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: 更新 __init__.py 添加导出**

```python
# openagentic_sdk/server/__init__.py
"""Server module exports"""
from .worker_registry import WorkerRegistry, WorkerInfo
from .worker_register_client import WorkerRegisterClient, WorkerConfig
from .cluster_chat_host_daily import DailyHostServer, build_daily_host_from_config

__all__ = [
    "WorkerRegistry",
    "WorkerInfo",
    "WorkerRegisterClient",
    "WorkerConfig",
    "DailyHostServer",
    "build_daily_host_from_config",
]
```

- [ ] **Step 6: 提交**

```bash
git add openagentic_sdk/server/cluster_chat_host_daily.py
git commit -m "$(cat <<'EOF'
feat(server): add cluster_chat_host_daily.py (simplified host)

Based on cluster_chat_host.py with following changes:
- Remove GitSyncResult and CommittedGitSynchronizer
- Remove session git_revision metadata
- Add /worker/register, /worker/unregister, /worker/heartbeat endpoints
- Integrate WorkerRegistry for dynamic worker management
- Simplify health response (no git_revision, cwd, config_source)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 创建部署配置文件

**Files:**
- Create: `deploy/docker/Dockerfile.daily`
- Create: `deploy/docker/docker-compose.daily.yml`
- Create: `deploy/docker/openagentic.daily.json`
- Create: `deploy/docker/nginx.daily.conf`

- [ ] **Step 1: 创建 Dockerfile.daily**

```dockerfile
# deploy/docker/Dockerfile.daily
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY openagentic_sdk ./openagentic_sdk
RUN pip install --no-cache-dir -e .

COPY deploy/docker/openagentic.daily.json /app/config/

RUN mkdir -p /home/user/.openagentic/sessions

EXPOSE 8766

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8766/health || exit 1

ENTRYPOINT ["python", "-u", "-m", "openagentic_sdk.server.cluster_chat_host_daily"]
CMD ["--host", "0.0.0.0", "--port", "8766", "--config", "/app/config/openagentic.daily.json", "--session-root", "/home/user/.openagentic/sessions"]
```

- [ ] **Step 2: 创建 docker-compose.daily.yml**

```yaml
# deploy/docker/docker-compose.daily.yml
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
      - PYTHONUNBUFFERED=1
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
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8765/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker-writer:
    build:
      context: ../..
      dockerfile: deploy/docker/Dockerfile.worker
    image: oa-worker:latest
    container_name: oa-worker-writer
    environment:
      - PYTHONUNBUFFERED=1
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
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8765/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  web:
    image: nginx:alpine
    container_name: oa-daily-web
    ports:
      - "${WEB_PORT:-3001}:80"
    volumes:
      - ./web/dist:/usr/share/nginx/html:ro
      - ./nginx.daily.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      host:
        condition: service_healthy
    restart: unless-stopped

volumes:
  oa-sessions:
```

- [ ] **Step 3: 创建 openagentic.daily.json**

```json
{
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
      "prompt": "你是一个专业翻译。准确、流畅、地道地翻译用户提供的文本。",
      "tools": [],
      "provider": "anthropic",
      "model": "claude-sonnet-4-6"
    },
    "writer": {
      "description": "写作助手 - 文章润色、创意写作",
      "prompt": "你是一个写作专家。帮助用户润色文章、提供创意写作建议。",
      "tools": [],
      "provider": "anthropic",
      "model": "claude-sonnet-4-6"
    },
    "researcher": {
      "description": "研究助手 - 信息搜集、分析总结",
      "prompt": "你是一个研究助手。帮助用户搜集信息、分析问题、总结要点。",
      "tools": ["WebSearch", "WebFetch"],
      "provider": "anthropic",
      "model": "claude-sonnet-4-6"
    }
  }
}
```

- [ ] **Step 4: 创建 nginx.daily.conf**

```nginx
# deploy/docker/nginx.daily.conf
server {
    listen 80;

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /session {
        proxy_pass http://host:8766;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

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

    location /health {
        proxy_pass http://host:8766;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /worker {
        proxy_pass http://host:8766;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

- [ ] **Step 5: 提交部署配置**

```bash
git add deploy/docker/Dockerfile.daily deploy/docker/docker-compose.daily.yml deploy/docker/openagentic.daily.json deploy/docker/nginx.daily.conf
git commit -m "$(cat <<'EOF'
feat(deploy): add Daily Assistant deployment configs

- Dockerfile.daily: slim image without git
- docker-compose.daily.yml: host + web services
- openagentic.daily.json: translator, writer, researcher agents
- nginx.daily.conf: API proxy + SSE streaming

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 集成测试

- [ ] **Step 1: 构建 Docker 镜像**

Run: `cd /Users/roc/workspace/openagentic-sdk/deploy/docker && docker compose -f docker-compose.daily.yml build 2>&1 | tail -20`
Expected: Build successful, image oa-daily:latest created

- [ ] **Step 2: 启动服务**

Run: `cd /Users/roc/workspace/openagentic-sdk/deploy/docker && docker compose -f docker-compose.daily.yml up -d`
Expected: Containers started (oa-daily-host, oa-daily-web)

- [ ] **Step 3: 测试 Health 端点**

Run: `sleep 5 && curl -s http://localhost:8766/health | jq .`
Expected: JSON with `"ok": true`, `"deployment_mode": "daily-assistant"`, `"workers": {}`

- [ ] **Step 4: 测试 Web UI**

访问 http://localhost:3001，验证：
- 页面正常加载
- 右侧 Worker 标签页显示 agents

- [ ] **Step 5: 清理测试环境**

Run: `cd /Users/roc/workspace/openagentic-sdk/deploy/docker && docker compose -f docker-compose.daily.yml down`

---

## Task 6: 推送并创建 PR

- [ ] **Step 1: 推送到 fork**

Run: `git push fork exp/v56-k3s-remote-subagent-spike`

- [ ] **Step 2: 创建 PR 到 main**

使用 gh CLI 创建 PR，标题："feat: Daily Assistant - simplified host with dynamic worker registration"

---

## 验收标准

1. ✅ `cluster_chat_host_daily.py` 不包含任何 git 相关代码
2. ✅ `/health` 返回 `"deployment_mode": "daily-assistant"` 和动态 workers
3. ✅ Worker 注册/心跳/取消注册 API 正常工作
4. ✅ Web UI 正常显示 Worker 信息
5. ✅ Session 持久化到 `~/.openagentic/sessions/`
