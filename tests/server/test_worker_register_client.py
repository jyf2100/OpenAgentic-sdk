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
