from __future__ import annotations

import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

FILES_SCHEMA = Path(__file__).parents[3] / "templates" / "files.schema.yaml"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
TOOL_NAMES = [
    "delete_docs",
    "describe",
    "list_changes",
    "list_match_words",
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
    "    paths: [alt/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "  - id: extra\n"
    "    paths: [extra/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
)
NO_SCRIPT_EXTRA = (
    "    converter: md\nconverters:\n  - id: md\n    run: [python3, scripts/missing.py]\n"
)
TERM_ROW = (
    "  - id: terms\n"
    "    paths: [terms/*.yaml]\n"
    "    schema: schemas/term.schema.yaml\n"
    "    alias_type: term\n"
)
TERM_SCHEMA = "title: 用語\ntype: object\n"
BROKEN_TERM = "id: broken\nname: 壊れた用語\ndescription: 型の違う別名\naliases: 3\n"
NONE_NAV = (
    "nav:\n"
    "  tabs:\n"
    "    - title: none\n"
    "      items:\n"
    "        - auto: {filter: {field: tags, op: eq, values: [none]}}\n"
)
SAMPLE_KIND_SCHEMA = "type: object\nproperties:\n  id: {type: string}\n  name: {type: string}\n"
LOOPBACK_V4 = "0100007F"
EXIT_TIMEOUT_SEC = 30
DOCS_TOOL_PREFIX = "mcp__plugin_dev-docs_dev-docs__"
# 使い分けは文書の MCP の instructions にある旨の行
POINTER_LINE = (
    "探す・読む・書くときの使い分けと書き方は、文書の MCP（dev-docs）の instructions にあります。"
)
# 文脈に置かない使い方・タグの行の語
USAGE_WORDS = (
    "describe(source)",
    'group_by="tags"',
    'source="*"',
    'view="full"',
    "管理用の YAML の行",
    "タグ:",
)
CONTEXT_MAX_CHARS = 1000
SESSION_PROMPT = "このセッションでは何も実行せず、「了解」とだけ答えてください。"
LEGACY_CONFIG = (
    'version: "1"\n'
    "name: legacy\n"
    "tags: tags.yaml\n"
    "documents:\n"
    "  - id: notes\n"
    "    paths: [docs/*.md]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    type: markdown\n"
    "  - id: rules\n"
    "    paths: [docs/*.yaml]\n"
    "    schema: schemas/sample.schema.yaml\n"
    "    type: yaml\n"
    "    metadata:\n"
    "      name: {type: ref, field: title}\n"
    "    defaults:\n"
    "      - paths: [docs/**]\n"
    "        tags: [doc]\n"
)
FILES_ROW = (
    "  - id: src\n"
    "    paths: [src/files.yaml]\n"
    "    schema: schemas/files.schema.yaml\n"
    "    records: files\n"
    "    body_file: path\n"
)


def test_normal(make_source: Callable[..., Any], serve: Callable[..., Any], tmp_path: Path) -> None:
    """端末の設定の 2 つの配信元を 1 プロセス・1 ポートで配信し始める（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False)
    # 実行
    served = serve(sample, notes)
    sample_docs = served.get("/_api/sources/sample/docs")
    notes_docs = served.get("/_api/sources/notes/docs")
    screen = served.get("/sample/docs/doc-1")
    admin = served.post_admin(INITIALIZE)
    # 検証
    assert served.listening_addresses() == {LOOPBACK_V4}
    assert sample_docs.status_code == 200
    assert notes_docs.status_code == 200
    assert screen.status_code == 200
    assert screen.headers["content-type"].startswith("text/html")
    assert '<div id="root">' in screen.text
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
        "      name: title\n"
        "  - id: src\n"
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
    assert any("metadata の列の欠け 1 件" in line and "name（title）" in line for line in warnings)
    assert any(
        "管理用の YAML に無いファイル 1 件" in line and "src/d.py" in line for line in warnings
    )
    assert any("ファイルが無い行 1 件" in line and "c.py" in line for line in warnings)
    assert found.data["items"][0]["values"]["name"] == "doc-2"


def test_error_when_source_config_legacy(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """前の形式の配信元を外し、違反と移し替えの案内をエラーログに残す（異常系）。"""
    # 準備
    sample = make_source("sample")
    legacy = make_source(
        "legacy", {"dev-docs.yaml": LEGACY_CONFIG, "tags.yaml": "python: Python の規約\n"}
    )
    # 実行
    served = serve(sample, legacy)
    legacy_docs = served.get("/_api/sources/legacy/docs")
    sample_docs = served.get("/_api/sources/sample/docs")
    # 検証
    errors = served.stderr()
    assert legacy_docs.status_code == 404
    assert sample_docs.status_code == 200
    assert "legacy: tags" in errors
    assert "legacy: documents[0].type" in errors
    assert "legacy: documents[1].type" in errors
    assert "legacy: documents[1].defaults" in errors
    assert "legacy: documents[1].metadata.name" in errors
    assert "設定のバージョンが古い" in errors
    assert "dev-docs migrate --source" in errors


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


def test_normal_when_started_by_session_start(
    tmp_path: Path,
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    add_worktree: Callable[..., Path],
    write_settings: Callable[..., Path],
    wait_for_server: Callable[..., None],
    list_mcp_tools: Callable[..., list[str]],
    serve_pid_count: Callable[[int], int],
) -> None:
    """SessionStart のフックが落ちている dev-docs を切り離して起動し、つなぎ直しを案内する（正常系）。"""
    # 準備
    clone = make_clone()
    sample = make_source("sample")
    sample.scope_write = [sample.folder]
    notes = make_source("notes", git=False, scope_read=[sample.folder, sample.folder / "**"])
    worktree = add_worktree(sample.folder, "x")
    settings = write_settings(sample, notes, clone=clone.clone)
    claude_home.set_env(DEV_DOCS_CONFIG=str(settings))
    port = claude_home.port
    before = serve_pid_count(port)
    # 実行
    first = claude_home.run(SESSION_PROMPT, cwd=worktree)
    wait_for_server(port)
    after_exit = serve_pid_count(port)
    second = claude_home.run(SESSION_PROMPT, cwd=worktree)
    # 検証
    exit_code, context = first.session_start_context()
    reconnected = sorted(name for name in second.init["tools"] if name.startswith(DOCS_TOOL_PREFIX))
    assert before == 0
    assert exit_code == 0
    assert "/mcp" in context
    assert "つなぎ直" in context
    assert after_exit == 1
    assert sorted(list_mcp_tools(port)) == TOOL_NAMES
    assert reconnected == [DOCS_TOOL_PREFIX + name for name in TOOL_NAMES]


def test_normal_when_session_context_added(
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    add_worktree: Callable[..., Path],
    serve: Callable[..., Any],
    serve_pid_count: Callable[[int], int],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """待ち受けているサーバーから、使える配信元・警告と instructions を指す 1 行を取ってセッションの文脈に入れる（正常系）。"""
    # 準備
    clone = make_clone()
    sample_files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(FILES_ROW, description="サンプルの配信元"),
            "schemas/files.schema.yaml": FILES_SCHEMA.read_text(encoding="utf-8"),
            "src/files.yaml": "files:\n  - path: a.py\n",
            "src/a.py": "a = 1\n",
            "src/extra.py": "x = 1\n",
        }
    )
    sample = make_source("sample", sample_files)
    sample.scope_write = [sample.folder]
    readable = [sample.folder, sample.folder / "**"]
    notes_files = sample_file_set(
        **{"dev-docs.yaml": sample_config_text(name="notes", description="メモの配信元")}
    )
    notes = make_source("notes", notes_files, git=False, scope_read=readable)
    old_files = sample_file_set(**{"dev-docs.yaml": sample_config_text(name="old", version="0")})
    old = make_source("old", old_files, git=False, scope_read=readable)
    worktree = add_worktree(sample.folder, "x")
    served = serve(sample, notes, old, clone=clone.clone, port=claude_home.port)
    claude_home.set_env(DEV_DOCS_CONFIG=str(served.settings))
    # 実行
    run = claude_home.run(SESSION_PROMPT, cwd=worktree)
    # 検証
    exit_code, context = run.session_start_context()
    assert exit_code == 0
    assert "- sample（読み書き）: サンプルの配信元" in context
    assert "- notes（読み取りだけ）: メモの配信元" in context
    assert POINTER_LINE in context
    assert [word for word in USAGE_WORDS if word in context] == []
    assert len(context) <= CONTEXT_MAX_CHARS
    assert "sample: 管理用の YAML に無いファイルが 1 件あります" in context
    assert "old: 設定のバージョンが古い" in context
    assert "つなぎ直" not in context
    assert serve_pid_count(claude_home.port) == 1


def test_error_when_session_start_cannot_start(
    tmp_path: Path, claude_home: Any, serve_pid_count: Callable[[int], int]
) -> None:
    """端末の設定を読めないと、dev-docs を起動せず、理由と global-setup の案内を文脈に入れる（異常系）。"""
    # 準備
    missing = tmp_path / "missing" / "settings.yaml"
    claude_home.set_env(DEV_DOCS_CONFIG=str(missing))
    # 実行
    run = claude_home.run(SESSION_PROMPT, cwd=tmp_path)
    # 検証
    exit_code, context = run.session_start_context()
    assert exit_code == 0
    assert not run.result["is_error"]
    assert str(missing) in context
    assert "/dev-docs:global-setup" in context
    assert serve_pid_count(claude_home.port) == 0


def _kind_row(kind: str) -> str:
    """`schemas/{kind}.schema.yaml` で `{kind}/*.yaml` を読む文書の種類の行を作る。"""
    return f"  - id: {kind}\n    paths: [{kind}/*.yaml]\n    schema: schemas/{kind}.schema.yaml\n"


def _kinds(result: Any) -> set[str]:
    """describe(source) の JSON の種類の ID を集める。"""
    return {kind["id"] for kind in result.data["kinds"]}


def test_normal_when_config_read_from_default_ref(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    run_git: Callable[..., str],
    commit_all: Callable[..., str],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """クローン本体が master のままでも、default_ref の develop の設定とスキーマで配信元を組み立てる（正常系）。"""
    # 準備
    sample = make_source("sample")
    run_git(sample.folder, "branch", "master")
    commit_all(
        sample.folder,
        {
            "dev-docs.yaml": sample_config_text(_kind_row("kind_a")),
            "schemas/kind_a.schema.yaml": SAMPLE_KIND_SCHEMA,
        },
        "docs: kind_a を加える",
    )
    run_git(sample.folder, "checkout", "master")
    worktree = sample.folder / ".claude" / "worktrees" / "develop"
    run_git(sample.folder, "worktree", "add", str(worktree), "develop")
    notes_files = sample_file_set(
        **{"dev-docs.yaml": sample_config_text(_kind_row("kind_n"), name="notes")}
    )
    notes_files["schemas/kind_n.schema.yaml"] = SAMPLE_KIND_SCHEMA
    notes = make_source("notes", notes_files, git=False, scope_read=[sample.folder])
    served = serve(sample, notes)
    cwd = str(sample.folder)
    # 実行
    first = served.call("describe", cwd=cwd, source="sample", format="json")
    commit_all(
        worktree,
        {
            "dev-docs.yaml": sample_config_text(_kind_row("kind_a") + _kind_row("kind_b")),
            "schemas/kind_b.schema.yaml": SAMPLE_KIND_SCHEMA,
        },
        "docs: kind_b を加える",
    )
    second = served.call("describe", cwd=cwd, source="sample", format="json")
    disk = served.call("describe", cwd=cwd, source="notes", format="json")
    # 検証
    assert "kind_a" in _kinds(first)
    assert not (sample.folder / "schemas" / "kind_a.schema.yaml").exists()
    assert {"kind_a", "kind_b"} <= _kinds(second)
    assert str(worktree) in {item["path"] for item in first.data["worktrees"]}
    assert "kind_n" in _kinds(disk)


def test_normal_when_alias_and_nav_warned(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
) -> None:
    """エイリアスのキーの違反と 0 件に当たる nav の条件を起動時に警告し、配信を始める（正常系）。"""
    # 準備
    files = sample_file_set(
        **{
            "dev-docs.yaml": sample_config_text(TERM_ROW + NONE_NAV),
            "schemas/term.schema.yaml": TERM_SCHEMA,
            "terms/broken.yaml": BROKEN_TERM,
        }
    )
    sample = make_source("sample", files)
    # 実行
    served = serve(sample)
    cwd = str(sample.folder)
    status = served.call_admin("status", format="json")
    found = served.call("search_docs", cwd=cwd, term="壊れた用語", format="json")
    words = served.call("list_match_words", cwd=cwd, source="sample", format="json")
    logs = served.stderr()
    # 検証
    sources = {item["id"]: item["status"] for item in status.data["sources"]}
    assert "terms/broken.yaml" in logs
    assert "文字列か文字列の並び" in logs
    assert "none" in logs
    assert sources["sample"] == "serving"
    assert not found.data.get("items")
    assert "壊れた用語" not in {item["word"] for item in words.data.get("words", [])}
