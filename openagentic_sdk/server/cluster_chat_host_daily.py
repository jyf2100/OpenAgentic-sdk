# openagentic_sdk/server/cluster_chat_host_daily.py
"""
Daily Assistant Host - 精简版 Host，支持动态 Worker 注册

基于 cluster_chat_host.py，但移除了 Git 同步功能，添加了 Worker 注册 API。
"""
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
from ..subagents.remote_http import HttpRemoteTaskDispatcher
from ..subagents.session_meta import build_authoritative_session_metadata
from ..tools.defaults import default_tool_registry
from .session_transcript_view import build_session_transcript
from .worker_registry import WorkerRegistry


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
    """Daily Assistant Host Server - 精简版，支持动态 Worker 注册"""

    base_options: OpenAgenticOptions
    session_store: FileSessionStore
    worker_registry: WorkerRegistry
    host: str = "127.0.0.1"
    port: int = 0
    host_node_name: str | None = None
    health_status: Mapping[str, Any] | None = None

    def make_server(self) -> ThreadingHTTPServer:
        options = self.base_options
        store = self.session_store
        host_node_name = self.host_node_name or ""
        worker_registry = self.worker_registry
        health_status = {
            "deployment_mode": "daily-assistant",
            **dict(self.health_status or {}),
        }
        hub = _EventHub()
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
                            hub.publish(
                                {
                                    "type": "session.event",
                                    "session_id": session_id,
                                    "event": event_to_dict(event),
                                }
                            )

                    asyncio.run(_query())
                except Exception as e:  # noqa: BLE001
                    hub.publish(
                        {
                            "type": "session.error",
                            "session_id": session_id,
                            "error": str(e),
                        }
                    )
                finally:
                    with running_lock:
                        running_abort.pop(session_id, None)
                    hub.publish(
                        {
                            "type": "session.done",
                            "session_id": session_id,
                        }
                    )

            threading.Thread(target=_run, name=f"oa-daily-host-{session_id}", daemon=True).start()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parts = _parse_request_target(self.path)

                # GET /health - 健康检查
                if parts == ["health"]:
                    payload: dict[str, Any] = {"ok": True}
                    if host_node_name:
                        payload["host_node_name"] = host_node_name
                    payload.update(health_status)
                    # 合并静态配置和动态注册的 workers
                    static_agents: dict[str, list[dict[str, Any]]] = {}
                    for agent_name, agent_def in options.agents.items():
                        node_name = "default"
                        if hasattr(agent_def, "executor") and agent_def.executor:
                            node_name = getattr(agent_def.executor, "node_name", "default") or "default"
                        if node_name not in static_agents:
                            static_agents[node_name] = []
                        static_agents[node_name].append({
                            "name": agent_name,
                            "description": getattr(agent_def, "description", "") or "",
                            "model": getattr(agent_def, "model", options.model) or options.model,
                            "tools": list(getattr(agent_def, "tools", []) or []),
                            "node_name": node_name,
                        })
                    # 动态注册的 workers 覆盖同名静态配置
                    payload["workers"] = worker_registry.merge_with_static(static_agents)
                    _write_json(self, 200, payload)
                    return

                # GET /event - SSE 事件流
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
                    except Exception:
                        return
                    finally:
                        hub.unsubscribe(q)

                # GET /session/{id}
                if len(parts) == 2 and parts[0] == "session":
                    session_id = parts[1]
                    try:
                        _ = store.session_dir(session_id)
                    except ValueError:
                        _write_json(self, 400, {"error": "invalid_session_id"})
                        return
                    info = _session_info(store, session_id)
                    if info is None:
                        _write_json(self, 404, {"error": "not_found"})
                        return
                    _write_json(self, 200, info)
                    return

                # GET /session/{id}/events
                if len(parts) == 3 and parts[0] == "session" and parts[2] == "events":
                    session_id = parts[1]
                    try:
                        entries = [event_to_dict(event) for event in store.read_events(session_id)]
                    except ValueError:
                        _write_json(self, 400, {"error": "invalid_session_id"})
                        return
                    _write_json(self, 200, {"session_id": session_id, "entries": entries})
                    return

                # GET /oa/transcript/session/{id}
                if len(parts) == 4 and parts[:3] == ["oa", "transcript", "session"]:
                    session_id = parts[3]
                    try:
                        payload = build_session_transcript(
                            store=store,
                            session_id=session_id,
                            source="host",
                            default_agent_name="host",
                        )
                    except ValueError:
                        _write_json(self, 400, {"error": "invalid_session_id"})
                        return
                    except FileNotFoundError:
                        _write_json(self, 404, {"error": "not_found"})
                        return
                    except Exception as exc:  # noqa: BLE001
                        _write_json(self, 500, {"error": "transcript_unavailable", "detail": str(exc)})
                        return
                    _write_json(self, 200, payload)
                    return

                # GET /oa/transcript/child/{node}/{id}
                if len(parts) == 5 and parts[:3] == ["oa", "transcript", "child"]:
                    target_node = parts[3]
                    session_id = parts[4]
                    dispatcher = options.remote_task_dispatcher
                    read_transcript = getattr(dispatcher, "read_transcript", None)
                    if not callable(read_transcript):
                        _write_json(self, 503, {"error": "transcript_unavailable"})
                        return
                    try:
                        status, payload = read_transcript(target_node=target_node, session_id=session_id)
                    except ConnectionError as exc:
                        _write_json(
                            self,
                            502,
                            {
                                "error": "worker_unreachable",
                                "target_node": target_node,
                                "detail": str(exc),
                            },
                        )
                        return
                    except Exception as exc:  # noqa: BLE001
                        _write_json(self, 500, {"error": "transcript_unavailable", "detail": str(exc)})
                        return
                    if not isinstance(payload, dict):
                        _write_json(self, 500, {"error": "transcript_unavailable", "detail": "invalid_transcript_payload"})
                        return
                    _write_json(self, int(status), payload)
                    return

                _write_json(self, 404, {"error": "not_found"})

            def do_POST(self):  # noqa: N802
                parts = _parse_request_target(self.path)

                # POST /session - 创建 session
                if parts == ["session"]:
                    body = _read_json(self)
                    if body is None:
                        return
                    metadata_raw = body.get("metadata")
                    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
                    title = body.get("title")
                    if isinstance(title, str) and title.strip():
                        metadata = {**metadata, "title": title.strip()}
                    session_metadata = build_authoritative_session_metadata(
                        cwd=options.cwd,
                        provider_name=getattr(options.provider, "name", "unknown"),
                        model=options.model,
                        setting_sources=options.setting_sources,
                        allowed_tools=options.allowed_tools,
                        extra=metadata,
                        host_node_name=host_node_name or None,
                    )
                    session_id = store.create_session(metadata=session_metadata)
                    _write_json(self, 200, _session_info(store, session_id) or {"id": session_id})
                    return

                # POST /session/{id}/prompt_async
                if len(parts) == 3 and parts[0] == "session" and parts[2] == "prompt_async":
                    session_id = parts[1]
                    try:
                        _ = store.session_dir(session_id)
                    except ValueError:
                        _write_json(self, 400, {"error": "invalid_session_id"})
                        return
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

                # POST /session/{id}/abort
                if len(parts) == 3 and parts[0] == "session" and parts[2] == "abort":
                    session_id = parts[1]
                    with running_lock:
                        abort_event = running_abort.get(session_id)
                    if abort_event is not None:
                        abort_event.set()
                    _write_json(self, 200, {"ok": True})
                    return

                # POST /worker/register - Worker 注册
                if parts == ["worker", "register"]:
                    body = _read_json(self)
                    if body is None:
                        return
                    node_name = body.get("node_name")
                    base_url = body.get("base_url")
                    agents = body.get("agents", [])
                    if not node_name or not isinstance(node_name, str):
                        _write_json(self, 400, {"error": "invalid_node_name"})
                        return
                    if not base_url or not isinstance(base_url, str):
                        _write_json(self, 400, {"error": "invalid_base_url"})
                        return
                    if not isinstance(agents, list):
                        _write_json(self, 400, {"error": "invalid_agents"})
                        return
                    worker_registry.register(
                        node_name=node_name,
                        base_url=base_url,
                        agents=agents,
                    )
                    _write_json(self, 200, {"ok": True, "node_name": node_name})
                    return

                # POST /worker/unregister - Worker 取消注册
                if parts == ["worker", "unregister"]:
                    body = _read_json(self)
                    if body is None:
                        return
                    node_name = body.get("node_name")
                    if not node_name or not isinstance(node_name, str):
                        _write_json(self, 400, {"error": "invalid_node_name"})
                        return
                    worker_registry.unregister(node_name)
                    _write_json(self, 200, {"ok": True, "node_name": node_name})
                    return

                # POST /worker/heartbeat - Worker 心跳
                if parts == ["worker", "heartbeat"]:
                    body = _read_json(self)
                    if body is None:
                        return
                    node_name = body.get("node_name")
                    if not node_name or not isinstance(node_name, str):
                        _write_json(self, 400, {"error": "invalid_node_name"})
                        return
                    success = worker_registry.heartbeat(node_name)
                    if success:
                        _write_json(self, 200, {"ok": True, "node_name": node_name})
                    else:
                        _write_json(self, 404, {"error": "worker_not_found", "node_name": node_name})
                    return

                _write_json(self, 404, {"error": "not_found"})

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                _ = format
                _ = args

        return ThreadingHTTPServer((self.host, int(self.port)), Handler)


class StaticNodeHttpRemoteTaskDispatcher:
    def __init__(self, *, node_urls: Mapping[str, str], timeout_s: float = 60.0) -> None:
        self._node_urls = {node_name: base_url.rstrip("/") for node_name, base_url in node_urls.items()}
        self._dispatchers = {
            node_name: HttpRemoteTaskDispatcher(base_url=base_url, timeout_s=timeout_s)
            for node_name, base_url in self._node_urls.items()
        }

    def bind_actor_tracing(self, tracing) -> None:
        for dispatcher in self._dispatchers.values():
            bind_actor_tracing = getattr(dispatcher, "bind_actor_tracing", None)
            if callable(bind_actor_tracing):
                bind_actor_tracing(tracing)

    def node_base_url(self, node_name: str) -> str | None:
        return self._node_urls.get(node_name)

    def read_transcript(self, *, target_node: str, session_id: str) -> tuple[int, dict[str, Any]]:
        dispatcher = self._dispatchers.get(target_node)
        if dispatcher is None:
            raise ConnectionError(f"no remote worker URL configured for node '{target_node}'")
        return dispatcher.read_transcript(target_node=target_node, session_id=session_id)

    async def dispatch(self, request):
        node_name = request.definition.executor.node_name or ""
        dispatcher = self._dispatchers.get(node_name)
        if dispatcher is None:
            raise RuntimeError(f"no remote worker URL configured for node '{node_name}'")
        return await dispatcher.dispatch(request)


def build_daily_host_from_config(
    *,
    repo_root: str,
    session_root: str,
    remote_config_path: str,
    env: Mapping[str, str] | None = None,
) -> tuple[OpenAgenticOptions, FileSessionStore, WorkerRegistry, dict[str, Any]]:
    """从配置构建 Daily Host

    Args:
        repo_root: 代码仓库根目录
        session_root: Session 存储目录
        remote_config_path: 远程集群配置文件路径
        env: 环境变量

    Returns:
        (options, session_store, worker_registry, health_status)
    """
    bootstrap = load_remote_cluster_bootstrap(repo_root=repo_root, config_path=remote_config_path, env=env)
    session_store = FileSessionStore(root_dir=Path(session_root))
    worker_registry = WorkerRegistry()
    provider = bootstrap.host_provider or UnavailableRemoteProvider()
    health_status = {
        "provider_ready": bootstrap.self_check.provider_ready,
        "provider_profiles": list(bootstrap.provider_profiles),
    }
    if bootstrap.self_check.errors:
        health_status["provider_errors"] = list(bootstrap.self_check.errors)
    options = OpenAgenticOptions(
        provider=provider,
        model=bootstrap.host_model or "gpt-5.4",
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
    return options, session_store, worker_registry, health_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily Assistant Host server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--session-root", required=True)
    parser.add_argument("--remote-config", default="")
    parser.add_argument("--host-node-name", default="")
    parser.add_argument("--host-node-name-env", default="")
    parser.add_argument("--node-url", action="append", default=[])
    args = parser.parse_args(argv)

    host_node_name = args.host_node_name or (os.environ.get(args.host_node_name_env, "") if args.host_node_name_env else "")
    node_urls = _parse_node_urls(args.node_url)
    worker_registry = WorkerRegistry()

    if args.remote_config:
        options, session_store, health_status = build_daily_host_from_config(
            repo_root=args.repo_root,
            session_root=args.session_root,
            remote_config_path=args.remote_config,
            env=os.environ,
        )
    else:
        from importlib import import_module

        session_store = FileSessionStore(root_dir=Path(args.session_root))
        options = OpenAgenticOptions(
            provider=UnavailableRemoteProvider(),
            model="fake",
            cwd=args.repo_root,
            project_dir=args.repo_root,
            tools=default_tool_registry(),
            permission_gate=PermissionGate(permission_mode="bypass"),
            session_store=session_store,
            agents={},
        )
        health_status = {}

    dispatcher = StaticNodeHttpRemoteTaskDispatcher(node_urls=node_urls) if node_urls else None
    options = replace(options, remote_task_dispatcher=dispatcher)

    httpd = DailyHostServer(
        base_options=options,
        session_store=session_store,
        worker_registry=worker_registry,
        host=args.host,
        port=args.port,
        host_node_name=host_node_name or None,
        health_status=health_status,
    ).make_server()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.server_close()
    return 0


def _parse_node_urls(raw_items: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in raw_items:
        node_name, sep, url = str(raw or "").partition("=")
        node_name = node_name.strip()
        url = url.strip()
        if not node_name or not sep or not url:
            raise SystemExit("--node-url entries must look like node-name=http://host:port")
        mapping[node_name] = url
    return mapping


if __name__ == "__main__":
    raise SystemExit(main())
