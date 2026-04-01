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
