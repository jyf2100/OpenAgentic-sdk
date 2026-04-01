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

        def handle_signal(_signum, _frame):
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
