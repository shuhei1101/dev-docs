from __future__ import annotations

import json
import shutil
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from dev_docs.features.prompt_doc.runtime import DEFAULT_PROMPTS_DIR, load_prompts
from dev_docs.server.mcp.result import mcp_prompt_ids, tool_prompt_id
from dev_docs.shared.yaml_io import load_yaml

from .conftest import MCP_HEADERS, SERVE_WAIT_SEC, IndexSource, MockIndex, sample_docs

ADMIN_TOOL_NAMES = ["restart", "status", "update"]
# ツールの名前 → 引数のスキーマのキー
ADMIN_TOOL_ARGUMENTS = {"restart": [], "status": ["format"], "update": []}
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
LISTEN_STATE = "0A"
TCP_TABLES = ("/proc/net/tcp", "/proc/net/tcp6")
LOOPBACK_V4 = "0100007F"
# 文に置かない言い回し
FORBIDDEN_WORDS = ("MUST", "必ず", "禁止")
START_GUIDE = "project-index を起動してから"


def _listening_addresses(port: int) -> set[str]:
    """ポートで待ち受けているローカルアドレス（16 進）を /proc から集める。"""
    found: set[str] = set()
    for table in TCP_TABLES:
        for line in Path(table).read_text(encoding="utf-8").splitlines()[1:]:
            columns = line.split()
            address, local_port = columns[1].split(":")
            if columns[3] == LISTEN_STATE and int(local_port, 16) == port:
                found.add(address)
    return found


def _mcp(port: int, path: str, payload: dict[str, Any]) -> httpx.Response:
    """MCP の JSON-RPC を 1 つ送る。"""
    return httpx.post(
        f"http://127.0.0.1:{port}{path}", headers=MCP_HEADERS, json=payload, timeout=10
    )


def _two_sources(mock: MockIndex) -> MockIndex:
    """sample と notes を配信中として返すように用意する。"""
    mock.serve("sample", IndexSource(docs={None: sample_docs()}))
    mock.serve("notes", IndexSource(docs={None: sample_docs()}, git=False))
    return mock


def test_normal(
    mock_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
) -> None:
    """project-index が配信している 2 つの配信元を画面で配信し始める（正常系）。"""
    # 準備
    settings = write_settings(_two_sources(mock_index).address)
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    # 実行
    sample = httpx.get(f"http://127.0.0.1:{port}/_api/sources/sample/docs", timeout=10)
    notes = httpx.get(f"http://127.0.0.1:{port}/_api/sources/notes/docs", timeout=10)
    docs_mcp = _mcp(port, "/mcp/", INITIALIZE)
    admin = _mcp(port, "/_admin/mcp/", INITIALIZE)
    admin_tools = _mcp(port, "/_admin/mcp/", {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    addresses = _listening_addresses(port)
    process.terminate()
    process.wait(timeout=15)
    output = process.stdout.read() if process.stdout else ""
    # 検証
    assert addresses == {LOOPBACK_V4}
    assert sample.status_code == 200
    assert notes.status_code == 200
    assert docs_mcp.status_code == 404
    assert admin.status_code == 200
    assert admin.json()["result"]["serverInfo"]
    assert (
        sorted(tool["name"] for tool in admin_tools.json()["result"]["tools"]) == ADMIN_TOOL_NAMES
    )
    lines = output.splitlines()
    assert f"http://127.0.0.1:{port}/" in lines
    assert {"sample", "notes"} <= set(lines)


def test_normal_when_project_index_unreachable(
    tmp_path: Path,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
) -> None:
    """project-index につながらなくても待ち受けを続け、標準エラーとエラーログに出す（正常系）。"""
    # 準備
    address = f"http://127.0.0.1:{free_port()}"
    settings = write_settings(address)
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    # 実行
    docs = httpx.get(f"http://127.0.0.1:{port}/_api/sources/sample/docs", timeout=10)
    status = _mcp(
        port,
        "/_admin/mcp/",
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "status", "arguments": {}},
        },
    )
    alive = process.poll() is None
    addresses = _listening_addresses(port)
    process.terminate()
    process.wait(timeout=15)
    error = process.stderr.read() if process.stderr else ""
    log = (tmp_path / "state" / "logs" / "dev-docs.log").read_text(encoding="utf-8")
    # 検証
    assert alive
    assert addresses == {LOOPBACK_V4}
    assert address in error
    assert START_GUIDE in error
    assert [line for line in log.splitlines() if " ERROR " in line and address in line]
    assert docs.status_code == 503
    assert status.status_code == 200
    assert status.json()["result"]["isError"] is False


def test_error_when_terminal_config_invalid(
    tmp_path: Path,
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
) -> None:
    """端末の設定がスキーマに違反すると待ち受けずに終わる（異常系）。"""
    # 準備
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        'version: "2"\nclone: /tmp/clone\nport: "not-a-number"\nproject_index: 127.0.0.1:8786\n',
        encoding="utf-8",
    )
    port = free_port()
    # 実行
    invalid = start_serve(settings, port)
    invalid_code = invalid.wait(timeout=SERVE_WAIT_SEC)
    invalid_error = invalid.stderr.read() if invalid.stderr else ""
    missing_file = tmp_path / "no-such-settings.yaml"
    missing = start_serve(missing_file, port)
    missing_code = missing.wait(timeout=SERVE_WAIT_SEC)
    missing_error = missing.stderr.read() if missing.stderr else ""
    # 検証
    assert invalid_code == 2
    assert f"{settings}: project_index" in invalid_error
    assert f"{settings}: port" in invalid_error
    assert missing_code == 2
    assert str(missing_file) in missing_error
    assert _listening_addresses(port) == set()


def test_error_when_port_in_use(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
) -> None:
    """ポートで待ち受けられないと終わる（異常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    port = free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", port))
        occupied.listen()
        # 実行
        process = start_serve(settings, port)
        code = process.wait(timeout=SERVE_WAIT_SEC)
        error = process.stderr.read() if process.stderr else ""
    # 検証
    assert code == 3
    assert str(port) in error
    assert "DEV_DOCS_PORT" in error


def test_normal_when_mcp_path_without_slash(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
) -> None:
    """スラッシュ無しの /_admin/mcp への POST に、リダイレクトを挟まずに MCP が応える（正常系）。"""
    # 準備
    settings = write_settings(sample_index.address)
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    # 実行
    admin = _mcp(port, "/_admin/mcp", INITIALIZE)
    admin_slash = _mcp(port, "/_admin/mcp/", INITIALIZE)
    process.terminate()
    process.wait(timeout=15)
    # 検証
    assert admin.status_code == 200
    assert admin.json()["result"]["serverInfo"]
    assert admin_slash.status_code == 200


def test_normal_when_xdg_dirs_set(
    sample_index: MockIndex,
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
    tmp_path: Path,
) -> None:
    """DEV_DOCS_CONFIG が無ければ XDG_CONFIG_HOME の下の端末の設定を読み、状態とログを決めた置き場に書く（正常系）。"""
    # 準備
    config_home = tmp_path / "xdg-config"
    state_home = tmp_path / "xdg-state"
    override = tmp_path / "override"
    configured = tmp_path / "configured"
    home = tmp_path / "home"
    settings = config_home / "dev-docs" / "settings.yaml"
    settings.parent.mkdir(parents=True)
    base = f'version: "2"\nclone: {tmp_path / "clone"}\nproject_index: {sample_index.address}\n'
    env = {
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_STATE_HOME": str(state_home),
        "HOME": str(home),
    }

    def serve_once(extra_env: dict[str, str]) -> int:
        port = free_port()
        process = start_serve(None, port, extra_env={**env, **extra_env})
        wait_until_serving(process, port)
        code = httpx.get(
            f"http://127.0.0.1:{port}/_api/sources/sample/docs", timeout=30
        ).status_code
        process.terminate()
        process.wait(timeout=15)
        return code

    # 実行
    settings.write_text(base, encoding="utf-8")
    first = serve_once({})
    first_log = (state_home / "dev-docs" / "logs" / "dev-docs.log").is_file()
    shutil.rmtree(state_home)
    settings.write_text(base + f"state_dir: {configured}\n", encoding="utf-8")
    second = serve_once({"DEV_DOCS_STATE_DIR": str(override)})
    settings.write_text(base, encoding="utf-8")
    third = serve_once({"XDG_STATE_HOME": "rel"})
    # 検証
    assert first == 200
    assert first_log
    assert second == 200
    assert (override / "logs" / "dev-docs.log").is_file()
    assert not configured.exists()
    assert third == 200
    assert (home / ".local" / "state" / "dev-docs" / "logs" / "dev-docs.log").is_file()
    assert not (Path.cwd() / "rel").exists()
    assert not state_home.exists()


def test_normal_when_mcp_text_from_prompts(
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
) -> None:
    """管理の MCP のツールの description をプロンプトの YAML から描画して返す（正常系）。"""
    # 準備
    port = free_port()
    process = start_serve(write_settings(sample_index.address), port)
    wait_until_serving(process, port)
    prompts = load_prompts(DEFAULT_PROMPTS_DIR, required=mcp_prompt_ids())
    # 実行
    tools = _mcp(port, "/_admin/mcp/", {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    process.terminate()
    process.wait(timeout=15)
    # 検証
    listed = tools.json()["result"]["tools"]
    descriptions = {tool["name"]: tool["description"] for tool in listed}
    assert descriptions == {
        name: prompts.render(tool_prompt_id("admin", name)) for name in ADMIN_TOOL_NAMES
    }
    assert [
        text for text in descriptions.values() if any(word in text for word in FORBIDDEN_WORDS)
    ] == []
    assert {
        tool["name"]: sorted(tool["inputSchema"].get("properties", {})) for tool in listed
    } == ADMIN_TOOL_ARGUMENTS


def test_error_when_prompt_invalid(
    tmp_path: Path,
    sample_index: MockIndex,
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """プロンプトの YAML がスキーマに違反すると待ち受けずに終わる（異常系）。"""
    # 準備
    prompts = tmp_path / "prompts"
    shutil.copytree(DEFAULT_PROMPTS_DIR, prompts)
    broken = prompts / "mcp" / "admin" / "tools" / "status.yaml"
    value = load_yaml(broken.read_text(encoding="utf-8"))
    del value["kind"]
    broken.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("DEV_DOCS_PROMPTS_DIR", str(prompts))
    settings = write_settings(sample_index.address)
    port = free_port()
    # 実行
    process = start_serve(settings, port)
    code = process.wait(timeout=SERVE_WAIT_SEC)
    error = process.stderr.read() if process.stderr else ""
    # 検証
    assert code == 4
    assert _listening_addresses(port) == set()
    assert str(broken) in error
    assert "kind" in error
