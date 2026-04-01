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
