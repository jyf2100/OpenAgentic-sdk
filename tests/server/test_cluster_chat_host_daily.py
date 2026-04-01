# tests/server/test_cluster_chat_host_daily.py
import json
from http.server import BaseHTTPRequestHandler
from unittest.mock import MagicMock

from openagentic_sdk.server.worker_registry import WorkerRegistry
from openagentic_sdk.server.cluster_chat_host_daily import (
    _parse_request_target,
    _write_json,
)


def test_parse_request_target():
    """测试 URL 解析"""
    assert _parse_request_target("/health") == ["health"]
    assert _parse_request_target("/worker/register") == ["worker", "register"]
    assert _parse_request_target("/session/abc123/events") == ["session", "abc123", "events"]
    assert _parse_request_target("/") == []
    assert _parse_request_target("") == []


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


def test_worker_registry_integration():
    """测试 WorkerRegistry 集成"""
    registry = WorkerRegistry()

    # 注册 worker
    registry.register(
        node_name="worker-translate",
        base_url="http://worker-translate:8765",
        agents=[{"name": "translator", "description": "翻译", "model": "gpt-4", "tools": []}],
    )

    workers = registry.get_all_workers()
    assert "worker-translate" in workers
    assert len(workers["worker-translate"]) == 1
    assert workers["worker-translate"][0]["name"] == "translator"

    # 心跳
    assert registry.heartbeat("worker-translate") is True

    # 取消注册
    registry.unregister("worker-translate")
    assert "worker-translate" not in registry.get_all_workers()
