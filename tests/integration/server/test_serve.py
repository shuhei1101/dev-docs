from __future__ import annotations

import logging
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    type: yaml\n"
TOOL_NAMES = [
    "delete_docs",
    "describe",
    "list_changes",
    "search_docs",
    "trace_related",
    "write_docs",
]
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
LOCAL_CONFIG_ROWS = (
    "  - id: sample\n"
    "    type: yaml\n"
    "    paths: [alt/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "  - id: extra\n"
    "    type: yaml\n"
    "    paths: [extra/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
)
NO_SCRIPT_EXTRA = (
    "    converter: md\nconverters:\n  - id: md\n    run: [python3, scripts/missing.py]\n"
)
FILES_SCHEMA = Path(__file__).parents[3] / "templates" / "files.schema.yaml"
LISTEN_STATE = "0A"
TCP_TABLES = ("/proc/net/tcp", "/proc/net/tcp6")
LOOPBACK_V4 = "0100007F"


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


def test_normal(
    make_source: Callable[..., Any],
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
    wait_until_serving: Callable[..., None],
) -> None:
    """端末の設定の 2 つの配信元を配信し始める（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False)
    settings = write_settings(sample, notes)
    port = free_port()
    process = start_serve(settings, port)
    wait_until_serving(process, port)
    # 実行
    sample_docs = httpx.get(f"http://127.0.0.1:{port}/_api/sources/sample/docs", timeout=10)
    notes_docs = httpx.get(f"http://127.0.0.1:{port}/_api/sources/notes/docs", timeout=10)
    tools = _mcp(port, "/mcp/", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    admin = _mcp(port, "/_admin/mcp/", INITIALIZE)
    addresses = _listening_addresses(port)
    process.terminate()
    process.wait(timeout=15)
    output = process.stdout.read() if process.stdout else ""
    # 検証
    assert addresses == {LOOPBACK_V4}
    assert sample_docs.status_code == 200
    assert notes_docs.status_code == 200
    assert sorted(tool["name"] for tool in tools.json()["result"]["tools"]) == TOOL_NAMES
    assert admin.status_code == 200
    assert admin.json()["result"]["serverInfo"]
    assert f"http://127.0.0.1:{port}/" in output
    assert "sample" in output
    assert "notes" in output


def test_normal_when_configs_merged(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """config の複数の YAML を上から順にマージする（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(description="基本の説明"),
            "dev-docs.local.yaml": (
                "name: sample\ndescription: 上書きの説明\ndocuments:\n" + LOCAL_CONFIG_ROWS
            ),
            "alt/doc-9.yaml": "id: doc-9\nname: 別の置き場の文書\n",
            "extra/doc-x.yaml": "id: doc-x\nname: 追加した行の文書\n",
        }
    )
    source = make_source("sample", files, config_names=("dev-docs.yaml", "dev-docs.local.yaml"))
    env = make_server(source)
    # 実行
    described = env.call("describe", cwd=str(source.folder))
    overridden = env.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "kind", "op": "eq", "values": ["sample"]},
        view="ids",
        format="json",
    )
    added = env.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "kind", "op": "eq", "values": ["extra"]},
        view="ids",
        format="json",
    )
    # 検証
    assert "上書きの説明" in described.text
    assert "基本の説明" not in described.text
    assert [item["id"] for item in overridden.data["items"]] == ["doc-9"]
    assert [item["id"] for item in added.data["items"]] == ["doc-x"]


def test_normal_when_config_version_old(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """古いバージョンの設定の配信元も配信し、警告を残す（正常系）。"""
    # 準備
    config = sample_config_text(name="old", version="0")
    old = make_source("old", sample_file_set(**{"dev-docs.yaml": config}))
    caplog.set_level(logging.WARNING)
    # 実行
    env = make_server(old)
    response = env.client.get("/_api/sources/old/docs")
    # 検証
    warnings = [record.getMessage() for record in caplog.records if "old" in record.getMessage()]
    assert response.status_code == 200
    assert any("0" in message and "1" in message for message in warnings)


def test_normal_when_source_invalid(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """設定がスキーマに違反する配信元と、スクリプトを実行できない配信元を外して配信する（正常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG})
    noscript_config = sample_config_text(NO_SCRIPT_EXTRA, name="noscript")
    noscript = make_source("noscript", sample_file_set(**{"dev-docs.yaml": noscript_config}))
    caplog.set_level(logging.ERROR)
    # 実行
    env = make_server(sample, broken, noscript)
    # 検証
    logs = caplog.text
    assert env.client.get("/_api/sources/broken/docs").status_code == 404
    assert env.client.get("/_api/sources/noscript/docs").status_code == 404
    assert env.client.get("/_api/sources/sample/docs").status_code == 200
    assert env.call("describe", cwd=str(sample.folder)).is_error is False
    assert "broken: documents[0].paths: 必須のキーが無い" in logs
    assert "noscript: converters[0]" in logs
    assert "scripts/missing.py" in logs
    assert env.client.post("/_admin/mcp/", headers=MCP_HEADERS, json=INITIALIZE).status_code == 200


def test_normal_when_metadata_out_of_sync(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ref の列の欠けと管理用の YAML のずれがあっても配信し、件数を警告のログに残す（正常系）。"""
    # 準備
    rows = (
        "    metadata:\n"
        "      name: {type: ref, field: title}\n"
        "  - id: src\n"
        "    type: yaml\n"
        "    paths: [src/files.yaml]\n"
        "    schema: schemas/files.schema.yaml\n"
        "    records: files\n"
        "    body_file: path\n"
    )
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(rows),
            "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
            "docs/doc-1.yaml": "id: doc-1\nname: 文書 1\ntitle: 文書 1\n",
            "docs/doc-2.yaml": "id: doc-2\nname: 文書 2\n",
            "src/files.yaml": "files:\n  - path: a.py\n  - path: c.py\n",
            "src/a.py": "a = 1\n",
            "src/d.py": "d = 4\n",
            "src/sub/e.py": "e = 5\n",
        }
    )
    sample = make_source("sample", files)
    clean = make_source(
        "clean", sample_file_set(**{"dev-docs.yaml": sample_config_text(name="clean")})
    )
    caplog.set_level(logging.WARNING)
    # 実行
    env = make_server(sample, clean)
    # 検証
    warnings = [record.getMessage() for record in caplog.records]
    sample_warnings = [message for message in warnings if message.startswith("sample:")]
    assert env.client.get("/_api/sources/sample/docs").status_code == 200
    assert len(sample_warnings) == 3
    assert any("ref の列の欠け 1 件" in m and "name（title）" in m for m in sample_warnings)
    assert any(
        "管理用の YAML に無いファイル 2 件" in m and "src/d.py" in m and "src/sub/e.py" in m
        for m in sample_warnings
    )
    assert any("ファイルが無い行 1 件" in m and "c.py" in m for m in sample_warnings)
    assert not any("src: src/files.yaml" in m for m in sample_warnings)
    assert [message for message in warnings if message.startswith("clean:")] == []


def test_error_when_terminal_config_invalid(
    tmp_path: Path,
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
) -> None:
    """端末の設定がスキーマに違反すると待ち受けずに終わる（異常系）。"""
    # 準備
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        'version: "1"\nclone: /tmp/clone\nport: "not-a-number"\nsources:\n  - id: a\n',
        encoding="utf-8",
    )
    port = free_port()
    # 実行
    invalid = start_serve(settings, port)
    invalid_code = invalid.wait(timeout=30)
    invalid_error = invalid.stderr.read() if invalid.stderr else ""
    missing_file = tmp_path / "no-such-settings.yaml"
    missing = start_serve(missing_file, port)
    missing_code = missing.wait(timeout=30)
    missing_error = missing.stderr.read() if missing.stderr else ""
    # 検証
    assert invalid_code == 2
    assert f"{settings}: sources[0].config" in invalid_error
    assert f"{settings}: port" in invalid_error
    assert missing_code == 2
    assert str(missing_file) in missing_error
    assert _listening_addresses(port) == set()


def test_error_when_port_in_use(
    make_source: Callable[..., Any],
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    start_serve: Callable[..., Any],
) -> None:
    """ポートで待ち受けられないと終わる（異常系）。"""
    # 準備
    settings = write_settings(make_source("sample"))
    port = free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", port))
        occupied.listen()
        # 実行
        process = start_serve(settings, port)
        code = process.wait(timeout=30)
        error = process.stderr.read() if process.stderr else ""
    # 検証
    assert code == 3
    assert str(port) in error
    assert "DEV_DOCS_PORT" in error
