from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from .conftest import MockIndex

SETTINGS_QUERY = "src/dev_docs/features/settings/query.py"
MIGRATION_STEPS = (
    "steps:\n  - op: add\n    path: port\n    value: 8781\n    description: ポートを足す\n"
)
UPDATE_CALL = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "update", "arguments": {}},
    }
)
NO_RESTART_WAIT_SEC = 3
# 保留した要求がモックへ届くのを待つ上限
REQUEST_WAIT_SEC = 30


def _wait_for_docs_request(mock: MockIndex) -> None:
    """文書の一覧の要求がモックへ届くまで待つ。"""
    deadline = time.monotonic() + REQUEST_WAIT_SEC
    while not any("/docs" in path for _, path, _ in mock.received):
        assert time.monotonic() < deadline, "文書の取得がモックへ届かなかった"
        time.sleep(0.05)


def _slow_update(port: int) -> tuple[socket.socket, bytes]:
    """`update` の要求の本文を途中まで送った接続と、残りの本文を返す。"""
    body = UPDATE_CALL.encode("utf-8")
    head = (
        "POST /_admin/mcp/ HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Accept: application/json, text/event-stream\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    sock = socket.create_connection(("127.0.0.1", port), timeout=30)
    sock.sendall(head + body[:10])
    return sock, body[10:]


def _read_result(sock: socket.socket) -> dict[str, Any]:
    """接続が閉じるまで応答を読み、JSON-RPC の結果の辞書を返す。"""
    chunks = []
    while chunk := sock.recv(65536):
        chunks.append(chunk)
    payload = b"".join(chunks).split(b"\r\n\r\n", 1)[1]
    result: dict[str, Any] = json.loads(payload)["result"]
    return result


def test_normal(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    dev_docs_clone: Any,
    start_serve_from_clone: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
    wait_for_restart: Callable[..., None],
) -> None:
    """新しい commit を取り込み、依存を入れ直して起動し直す（正常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve_from_clone(dev_docs_clone.clone, settings, port)
    wait_until_serving(process, port)
    upstream = dev_docs_clone.push_upstream(dev_docs_clone.bump_version("0.3.0"), "bump")
    started = started_count(state_dir)
    # 実行
    with httpx.Client(timeout=300) as client:
        result = call_tool(client, port, "/_admin/mcp/", "update")
    wait_for_restart(state_dir, port, started)
    with httpx.Client(timeout=30) as client:
        status = call_tool(client, port, "/_admin/mcp/", "status", format="json")
    # 検証
    assert result["structuredContent"] == {
        "previous_version": "0.0.0",
        "version": "0.3.0",
        "updated": True,
        "migration_needed": False,
        "restarting": True,
    }
    assert dev_docs_clone.head() == upstream
    assert status["structuredContent"]["version"] == "0.3.0"


def test_normal_when_up_to_date(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    dev_docs_clone: Any,
    start_serve_from_clone: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
) -> None:
    """上流に新しい commit が無ければ、何も変えずに返す（正常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve_from_clone(dev_docs_clone.clone, settings, port)
    wait_until_serving(process, port)
    started = started_count(state_dir)
    head = dev_docs_clone.head()
    # 実行
    with httpx.Client(timeout=300) as client:
        result = call_tool(client, port, "/_admin/mcp/", "update")
    time.sleep(NO_RESTART_WAIT_SEC)
    # 検証
    data = result["structuredContent"]
    assert data["updated"] is False
    assert data["restarting"] is False
    assert data["version"] == data["previous_version"]
    assert dev_docs_clone.head() == head
    assert started_count(state_dir) == started
    assert process.poll() is None


def test_normal_when_migration_needed(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    dev_docs_clone: Any,
    start_serve_from_clone: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
) -> None:
    """新しいバージョンに移し替えの手順があると、再起動せずに返す（正常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve_from_clone(dev_docs_clone.clone, settings, port)
    wait_until_serving(process, port)
    query = (dev_docs_clone.work / SETTINGS_QUERY).read_text(encoding="utf-8")
    dev_docs_clone.push_upstream(
        {
            **dev_docs_clone.bump_version("0.3.0"),
            SETTINGS_QUERY: query.replace('SETTINGS_VERSION = "2"', 'SETTINGS_VERSION = "3"'),
            "src/dev_docs/migrations/settings/3/steps.yaml": MIGRATION_STEPS,
        },
        "migration",
    )
    started = started_count(state_dir)
    before = settings.read_text(encoding="utf-8")
    # 実行
    with httpx.Client(timeout=300) as client:
        result = call_tool(client, port, "/_admin/mcp/", "update")
    time.sleep(NO_RESTART_WAIT_SEC)
    with httpx.Client(timeout=30) as client:
        status = call_tool(client, port, "/_admin/mcp/", "status", format="json")
    # 検証
    data = result["structuredContent"]
    assert data["updated"] is True
    assert data["migration_needed"] is True
    assert data["restarting"] is False
    assert settings.read_text(encoding="utf-8") == before
    assert status["structuredContent"]["version"] == "0.0.0"
    assert started_count(state_dir) == started


def test_error_when_pull_fails(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    dev_docs_clone: Any,
    start_serve_from_clone: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
) -> None:
    """fast-forward できないと、クローンに触らず再起動もしない（異常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve_from_clone(dev_docs_clone.clone, settings, port)
    wait_until_serving(process, port)
    dev_docs_clone.run_git(dev_docs_clone.clone, "commit", "--allow-empty", "-m", "local")
    head = dev_docs_clone.head()
    dev_docs_clone.push_upstream(dev_docs_clone.bump_version("0.3.0"), "upstream")
    started = started_count(state_dir)
    # 実行
    with httpx.Client(timeout=300) as client:
        result = call_tool(client, port, "/_admin/mcp/", "update")
    time.sleep(NO_RESTART_WAIT_SEC)
    # 検証
    text = result["content"][0]["text"]
    assert result["isError"] is True
    assert text.startswith("UpdateFailedError")
    assert "git pull --ff-only" in text
    assert "fast-forward" in text
    assert dev_docs_clone.head() == head
    assert started_count(state_dir) == started
    assert process.poll() is None


def test_error_when_restart_in_progress(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    dev_docs_clone: Any,
    start_serve_from_clone: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
    wait_for_restart: Callable[..., None],
) -> None:
    """`restart` の停止を待っている間に `update` を呼ぶと、クローンに触らず断る（異常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve_from_clone(dev_docs_clone.clone, settings, port)
    wait_until_serving(process, port)
    head = dev_docs_clone.head()
    dev_docs_clone.push_upstream(dev_docs_clone.bump_version("0.3.0"), "upstream")
    started = started_count(state_dir)
    sample_index.received.clear()
    sample_index.hold.clear()

    def fetch() -> None:
        httpx.get(f"http://127.0.0.1:{port}/_api/sources/sample/docs", timeout=60)

    pending = threading.Thread(target=fetch)
    # 実行（project-index が応答しない文書の取得の途中で、update の要求を送りかけたまま restart を呼び、残りを送る）
    pending.start()
    _wait_for_docs_request(sample_index)
    sock, rest = _slow_update(port)
    with httpx.Client(timeout=30) as client:
        call_tool(client, port, "/_admin/mcp/", "restart")
    sock.sendall(rest)
    result = _read_result(sock)
    sock.close()
    sample_index.hold.set()
    pending.join(timeout=60)
    wait_for_restart(state_dir, port, started)
    # 検証
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("RestartInProgressError")
    assert dev_docs_clone.head() == head
    assert process.poll() is None
