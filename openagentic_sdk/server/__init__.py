from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

__all__ = [
    "OpenAgenticHttpServer",
    "serve_http",
    "ClusterChatClient",
    "ClusterChatRuntime",
    "ClusterChatHostServer",
    "DailyHostServer",
    "WorkerRegistry",
    "WorkerInfo",
    "WorkerRegisterClient",
    "WorkerConfig",
]

# Type annotations for pyright
if TYPE_CHECKING:
    from .cluster_chat_client import ClusterChatClient, ClusterChatRuntime
    from .cluster_chat_host import ClusterChatHostServer
    from .cluster_chat_host_daily import DailyHostServer
    from .worker_registry import WorkerInfo, WorkerRegistry
    from .worker_register_client import WorkerConfig, WorkerRegisterClient
    from .http_server import OpenAgenticHttpServer, serve_http


def __getattr__(name: str):
    if name in {"ClusterChatClient", "ClusterChatRuntime"}:
        module = import_module(".cluster_chat_client", __name__)
    elif name == "ClusterChatHostServer":
        module = import_module(".cluster_chat_host", __name__)
    elif name == "DailyHostServer":
        module = import_module(".cluster_chat_host_daily", __name__)
    elif name in {"OpenAgenticHttpServer", "serve_http"}:
        module = import_module(".http_server", __name__)
    elif name in {"WorkerRegistry", "WorkerInfo"}:
        module = import_module(".worker_registry", __name__)
    elif name in {"WorkerRegisterClient", "WorkerConfig"}:
        module = import_module(".worker_register_client", __name__)
    else:
        raise AttributeError(name)
    value = getattr(module, name)
    globals()[name] = value
    return value
