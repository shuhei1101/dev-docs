from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from .conftest import MCP_HEADERS, MockIndex

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "integration-test", "version": "0"},
    },
}
# 保留した要求がモックへ届くのを待つ上限
REQUEST_WAIT_SEC = 30


def _wait_for_docs_request(mock: MockIndex) -> None:
    """文書の取得が sample の配信元へ送った最初の要求（配信元の設定・リビジョン）がモックへ届くまで待つ。"""
    deadline = time.monotonic() + REQUEST_WAIT_SEC
    while not any(path.startswith("/sources/sample/") for _, path, _ in mock.received):
        assert time.monotonic() < deadline, "文書の取得がモックへ届かなかった"
        time.sleep(0.05)


def test_normal(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
    wait_for_restart: Callable[..., None],
) -> None:
    """応答を返した後に起動し直し、同じプロセス ID で待ち受ける（正常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    started = started_count(state_dir)
    # 実行（/_admin/mcp の接続を張ったまま restart を呼ぶ）
    with httpx.Client(timeout=15) as client:
        client.post(f"http://127.0.0.1:{port}/_admin/mcp/", headers=MCP_HEADERS, json=INITIALIZE)
        restarted = call_tool(client, port, "/_admin/mcp/", "restart")
    wait_for_restart(state_dir, port, started)
    with httpx.Client(timeout=15) as client:
        status = call_tool(client, port, "/_admin/mcp/", "status", format="json")
        reopened = client.post(
            f"http://127.0.0.1:{port}/_admin/mcp/", headers=MCP_HEADERS, json=INITIALIZE
        )
    # 検証
    sources = {item["id"]: item for item in status["structuredContent"]["sources"]}
    assert process.poll() is None
    assert restarted["structuredContent"] == {"pid": process.pid, "restarting": True}
    assert status["structuredContent"]["pid"] == process.pid
    assert sources["sample"]["status"] == "serving"
    assert started_count(state_dir) == started + 1
    assert reopened.status_code == 200


def test_error_when_restart_in_progress(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
    wait_for_restart: Callable[..., None],
) -> None:
    """停止を待っている間に 2 回目の restart を呼ぶと断る（異常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    started = started_count(state_dir)
    sample_index.received.clear()
    sample_index.hold.clear()
    results: dict[str, dict[str, Any]] = {}

    def fetch() -> None:
        httpx.get(f"http://127.0.0.1:{port}/_api/sources/sample/docs", timeout=60)

    def restart(label: str) -> None:
        with httpx.Client(timeout=30) as client:
            results[label] = call_tool(client, port, "/_admin/mcp/", "restart")

    # 実行（project-index が応答しない文書の取得の途中で、restart を 2 つ同時に呼ぶ）
    pending = threading.Thread(target=fetch)
    pending.start()
    _wait_for_docs_request(sample_index)
    restarts = [threading.Thread(target=restart, args=(label,)) for label in ("first", "second")]
    for thread in restarts:
        thread.start()
    for thread in restarts:
        thread.join(timeout=60)
    sample_index.hold.set()
    pending.join(timeout=60)
    wait_for_restart(state_dir, port, started)
    # 検証
    outcomes = sorted(
        (bool(results[label].get("isError")), results[label]["content"][0]["text"])
        for label in ("first", "second")
    )
    assert outcomes[0][0] is False
    assert outcomes[1][0] is True
    assert outcomes[1][1].startswith("RestartInProgressError")
    assert started_count(state_dir) == started + 1
    assert process.poll() is None
