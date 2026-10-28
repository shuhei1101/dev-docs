from __future__ import annotations

import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

FILES_SCHEMA = Path(__file__).parents[3] / "templates" / "files.schema.yaml"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    type: yaml\n"
TOOL_NAMES = [
    "delete_docs",
    "describe",
    "list_changes",
    "search_docs",
    "trace_related",
    "write_docs",
]
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "e2e-test", "version": "0"},
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
LOOPBACK_V4 = "0100007F"
EXIT_TIMEOUT_SEC = 30


def test_normal(make_source: Callable[..., Any], serve: Callable[..., Any], tmp_path: Path) -> None:
    """端末の設定の 2 つの配信元を 1 プロセス・1 ポートで配信し始める（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False)
    # 実行
    served = serve(sample, notes)
    sample_docs = served.get("/_api/sources/sample/docs")
    notes_docs = served.get("/_api/sources/notes/docs")
    admin = served.post_admin(INITIALIZE)
    # 検証
    assert served.listening_addresses() == {LOOPBACK_V4}
    assert sample_docs.status_code == 200
    assert notes_docs.status_code == 200
    assert sorted(served.tool_names()) == TOOL_NAMES
    assert admin.status_code == 200
    assert admin.json()["result"]["serverInfo"]
    assert f"http://127.0.0.1:{served.port}/" in served.stdout()
    assert "sample" in served.stdout()
    assert "notes" in served.stdout()


def test_normal_when_configs_merged(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """設定の YAML を上から順に重ねて配信する（正常系）。"""
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
    served = serve(source)
    # 実行
    described = served.call("describe", cwd=str(source.folder))
    overridden = served.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "kind", "op": "eq", "values": ["sample"]},
        view="ids",
        format="json",
    )
    added = served.call(
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
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """設定のバージョンが古い配信元も配信し、警告を残す（正常系）。"""
    # 準備
    config = sample_config_text(name="old", version="0")
    old = make_source("old", sample_file_set(**{"dev-docs.yaml": config}))
    # 実行
    served = serve(old)
    response = served.get("/_api/sources/old/docs")
    # 検証
    warnings = [
        line for line in served.stderr().splitlines() if "WARNING" in line and "old" in line
    ]
    assert response.status_code == 200
    assert any("0" in line and "1" in line for line in warnings)


def test_normal_when_metadata_out_of_sync(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """文書のメタデータと管理用の YAML がずれていても配信し、件数を警告のログに残す（正常系）。"""
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
            "docs/doc-2.yaml": "id: doc-2\n",
            "src/files.yaml": "files:\n  - path: a.py\n  - path: c.py\n",
            "src/a.py": "a = 1\n",
            "src/d.py": "d = 4\n",
        }
    )
    sample = make_source("sample", files)
    # 実行
    served = serve(sample)
    docs = served.get("/_api/sources/sample/docs")
    found = served.call(
        "search_docs",
        cwd=str(sample.folder),
        filter={"field": "id", "op": "eq", "values": ["doc-2"]},
        view="summary",
        format="json",
    )
    # 検証
    warnings = [
        line
        for line in served.stderr().splitlines()
        if "WARNING" in line and "dev_docs.main: sample:" in line
    ]
    assert docs.status_code == 200
    assert len(warnings) == 3
    assert any("ref の列の欠け 1 件" in line and "name（title）" in line for line in warnings)
    assert any(
        "管理用の YAML に無いファイル 1 件" in line and "src/d.py" in line for line in warnings
    )
    assert any("ファイルが無い行 1 件" in line and "c.py" in line for line in warnings)
    assert found.data["items"][0]["values"]["name"] == "doc-2"


def test_error_when_source_config_invalid(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """設定の検証に失敗した配信元を外し、他の配信元と管理の MCP は配信する（異常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG})
    # 実行
    served = serve(sample, broken)
    broken_docs = served.get("/_api/sources/broken/docs")
    sample_docs = served.get("/_api/sources/sample/docs")
    described = served.call("describe", cwd=str(sample.folder))
    admin = served.post_admin(INITIALIZE)
    # 検証
    assert broken_docs.status_code == 404
    assert sample_docs.status_code == 200
    assert not described.is_error
    assert admin.status_code == 200
    assert "broken: documents[0].paths: 必須のキーが無い" in served.stderr()


def test_error_when_script_not_executable(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """スクリプトを実行できない配信元を外して配信する（異常系）。"""
    # 準備
    sample = make_source("sample")
    config = sample_config_text(NO_SCRIPT_EXTRA, name="noscript")
    noscript = make_source("noscript", sample_file_set(**{"dev-docs.yaml": config}))
    # 実行
    served = serve(sample, noscript)
    noscript_docs = served.get("/_api/sources/noscript/docs")
    sample_docs = served.get("/_api/sources/sample/docs")
    # 検証
    assert noscript_docs.status_code == 404
    assert sample_docs.status_code == 200
    assert "noscript: converters[0]" in served.stderr()
    assert "scripts/missing.py" in served.stderr()


def test_error_when_terminal_config_invalid(
    tmp_path: Path,
    free_port: Callable[[], int],
    launch: Callable[..., Any],
) -> None:
    """端末の設定がスキーマに違反すると、違反を標準エラーに出して待ち受けずに終わる（異常系）。"""
    # 準備
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        'version: "1"\nclone: /tmp/clone\nport: "not-a-number"\nsources:\n  - id: a\n',
        encoding="utf-8",
    )
    port = free_port()
    # 実行
    served = launch(settings, port)
    code = served.process.wait(timeout=EXIT_TIMEOUT_SEC)
    # 検証
    assert code != 0
    assert f"{settings}: sources[0].config" in served.stderr()
    assert f"{settings}: port" in served.stderr()
    assert served.listening_addresses() == set()


def test_error_when_port_in_use(
    make_source: Callable[..., Any],
    write_settings: Callable[..., Path],
    free_port: Callable[[], int],
    launch: Callable[..., Any],
) -> None:
    """ポートが使用中だと、ポートと DEV_DOCS_PORT を標準エラーに出して終わる（異常系）。"""
    # 準備
    settings = write_settings(make_source("sample"))
    port = free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", port))
        occupied.listen()
        # 実行
        served = launch(settings, port)
        code = served.process.wait(timeout=EXIT_TIMEOUT_SEC)
    # 検証
    assert code != 0
    assert str(port) in served.stderr()
    assert "DEV_DOCS_PORT" in served.stderr()
