from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
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
SLOW_CONFIG = (
    "name: slow\n"
    "documents:\n"
    "  - id: note\n"
    "    type: yaml\n"
    "    paths: [docs/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    converter: sleepy\n"
    "converters:\n"
    "  - id: sleepy\n"
    "    run: [python3, scripts/sleepy.py]\n"
)
SLEEPY = "import sys\nimport time\nsys.stdin.read()\ntime.sleep(3)\nprint('# 眠ってから返した')\n"


def test_normal(
    make_source: Callable[..., Any],
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
    sample = make_source("sample")
    settings = write_settings(sample)
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    started = started_count(state_dir)
    # 実行（/mcp の接続を張ったまま restart を呼ぶ）
    with httpx.Client(timeout=15) as client:
        client.post(f"http://127.0.0.1:{port}/mcp/", headers=MCP_HEADERS, json=INITIALIZE)
        restarted = call_tool(client, port, "/_admin/mcp/", "restart")
    wait_for_restart(state_dir, port, started)
    with httpx.Client(timeout=15) as client:
        status = call_tool(client, port, "/_admin/mcp/", "status", format="json")
        reopened = client.post(
            f"http://127.0.0.1:{port}/mcp/", headers=MCP_HEADERS, json=INITIALIZE
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
    make_source: Callable[..., Any],
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    sample_file_set: Callable[..., dict[str, str]],
    call_tool: Callable[..., dict[str, Any]],
    started_count: Callable[[Path], int],
    wait_for_restart: Callable[..., None],
) -> None:
    """停止を待っている間に 2 回目の restart を呼ぶと断る（異常系）。"""
    # 準備
    files = sample_file_set(
        **{"dev-docs.yaml": SLOW_CONFIG, "scripts/sleepy.py": SLEEPY},
    )
    slow = make_source("slow", files, git=False)
    settings = write_settings(slow, extra="script_timeout_sec: 4")
    state_dir = settings.parent / "state"
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    started = started_count(state_dir)
    results: dict[str, dict[str, Any]] = {}

    def convert() -> None:
        with httpx.Client(timeout=30) as client:
            results["convert"] = call_tool(
                client,
                port,
                "/_admin/mcp/",
                "try_convert",
                path=str(slow.folder),
                file="docs/doc-1.yaml",
            )

    def restart(label: str) -> None:
        with httpx.Client(timeout=30) as client:
            results[label] = call_tool(client, port, "/_admin/mcp/", "restart")

    # 実行（眠る変換の途中で、restart を 2 つ同時に呼ぶ）
    threads = [threading.Thread(target=convert)]
    threads[0].start()
    time.sleep(1)
    threads += [threading.Thread(target=restart, args=(label,)) for label in ("first", "second")]
    for thread in threads[1:]:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
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
