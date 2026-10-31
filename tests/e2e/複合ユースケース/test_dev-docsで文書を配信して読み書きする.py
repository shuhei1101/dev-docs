from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from dev_docs.shared.hashing import content_hash

DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}
NEW_VERSION = "0.3.0"
TOOL_NAMES = [
    "delete_docs",
    "describe",
    "list_changes",
    "list_match_words",
    "search_docs",
    "trace_related",
    "write_docs",
]
SYNC_ZERO = {"missing_refs": 0, "unindexed_files": 0, "missing_body_files": 0}
SESSION_PROMPT = "このセッションでは何も実行せず、「了解」とだけ答えてください。"
LOCATION_PATTERN = r"場所|パス|settings\.yaml"
WRITE_PATTERN = r"scope\.write|書き込める"
READ_PATTERN = r"scope\.read|読める"
NOT_ANSWERED = "なし（scope.write は答えない）"
BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    schema: schemas/sample.schema.yaml\n"
DOC_URL = "http://127.0.0.1:{port}/_api/sources/sample/docs/docs/doc-1"
LIST_URL = "http://127.0.0.1:{port}/_api/sources/sample/docs"


def test_normal(
    tmp_path: Path,
    claude_home: Any,
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
    load_yaml_file: Callable[[Path], Any],
    snapshot: Callable[[Path], dict[str, bytes]],
    call_mcp_tool: Callable[..., Any],
    update_server: Callable[[int], Any],
    wait_for_server: Callable[..., None],
    wait_for_new_version: Callable[..., Any],
    list_mcp_tools: Callable[..., list[str]],
    serve_pid_count: Callable[[int], int],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    sample_doc_text: Callable[..., str],
) -> None:
    """dev-docs を入れ、配信元を並べ、読み書き・変更のレビュー・保守・更新を経ても配信が続く（正常系）。"""
    # 準備
    port = claude_home.port
    clone = make_clone(sync=False)
    sample_files = sample_file_set(
        **{"dev-docs.yaml": sample_config_text(description="サンプルの配信元")}
    )
    sample = make_source("sample", sample_files)
    notes_files = sample_file_set(
        **{"dev-docs.yaml": sample_config_text(name="notes", description="メモの配信元")}
    )
    notes = make_source("notes", notes_files, git=False)
    worktree = add_worktree(sample.folder, "x")
    settings = tmp_path / "terminal" / "settings.yaml"
    settings.parent.mkdir()
    cwd = {"cwd": str(worktree)}

    def docs(name: str, **arguments: Any) -> Any:
        """sample のワークツリーから文書の MCP のツールを呼ぶ。"""
        return call_mcp_tool(port, "/mcp/", name, **cwd, **arguments)

    def admin(name: str, **arguments: Any) -> Any:
        """管理の MCP のツールを呼ぶ。"""
        return call_mcp_tool(port, "/_admin/mcp/", name, **arguments)

    # S0: dev-docs を入れる
    installed = claude_home.run(
        f"/dev-docs:global-setup {clone.clone}",
        cwd=tmp_path,
        answers=[(LOCATION_PATTERN, str(settings))],
    )
    wait_for_server(port)
    terminal = load_yaml_file(settings)
    assert not installed.result["is_error"]
    assert terminal["clone"] == str(clone.clone)
    assert claude_home.settings_json()["env"]["DEV_DOCS_CONFIG"] == str(settings)
    assert serve_pid_count(port) == 1
    # S1: 配信元を追加する（sample は読み書き、notes は読み取りだけ）
    added_sample = claude_home.run(
        f"/dev-docs:setup {sample.folder}",
        cwd=sample.folder,
        answers=[(WRITE_PATTERN, str(sample.folder)), (READ_PATTERN, f"{sample.folder}/**")],
    )
    added_notes = claude_home.run(
        f"/dev-docs:setup {notes.folder}",
        cwd=notes.folder,
        answers=[(WRITE_PATTERN, NOT_ANSWERED), (READ_PATTERN, f"{sample.folder}/**")],
    )
    # S2: 新しいセッションの文脈に、使える配信元と短い使い方が入る
    session = claude_home.run(SESSION_PROMPT, cwd=worktree)
    exit_code, context = session.session_start_context()
    assert not added_sample.result["is_error"]
    assert not added_notes.result["is_error"]
    assert exit_code == 0
    assert "- sample（読み書き）" in context
    assert "- notes（読み取りだけ）" in context
    assert "describe(source)" in context
    assert "つなぎ直" not in context
    # 端末の設定に並べた配信元は、管理の MCP の状態・検査・変換で確かめられる
    status = admin("status", format="json").data
    checked = admin("check_project", path=str(sample.folder), format="json")
    main_before = snapshot(sample.folder)
    converted = admin("try_convert", path=str(sample.folder), file="docs/doc-1.yaml")
    assert {row["id"] for row in load_yaml_file(settings)["sources"]} == {"sample", "notes"}
    assert checked.data.get("violations", []) == []
    assert checked.data["sync"] == SYNC_ZERO
    assert "文書 1" in converted.data["markdown"]
    assert snapshot(sample.folder) == main_before
    assert {s["id"] for s in status["sources"] if s["status"] == "serving"} == {"sample", "notes"}
    tools = list_mcp_tools(port)
    assert sorted(tools) == TOOL_NAMES
    # S3: エージェントが調べる
    described = docs("describe")
    in_worktree = docs("search_docs", view="ids", format="json")
    across = docs("search_docs", source="*", format="json")
    assert "| sample | write" in described.text
    assert "| notes | read |" in described.text
    assert [item["id"] for item in in_worktree.data["items"]] == ["doc-1", "doc-2"]
    assert {item["source"] for item in across.data["items"]} == {"sample", "notes"}
    # S4: エージェントが書き込む（sample のワークツリーだけに入り、notes は断られる）
    target = worktree / "docs" / "doc-1.yaml"
    clone_text = (sample.folder / "docs" / "doc-1.yaml").read_text(encoding="utf-8")
    notes_before = snapshot(notes.folder)
    commits = int(run_git(worktree, "rev-list", "--count", "HEAD"))
    parent = run_git(worktree, "rev-parse", "HEAD").strip()
    read = docs("search_docs", filter=DOC_1, view="summary", format="json")
    read_version = read.data["items"][0]["values"]["version"]
    update = {"op": "update", "id": "doc-1", "expected_version": read_version}
    written = docs("write_docs", operations=[{**update, "set": {"name": "新しい名前"}}])
    refused = docs(
        "write_docs", source="notes", operations=[{**update, "set": {"name": "新しい名前"}}]
    )
    assert written.data["applied"] is True
    assert "name: 新しい名前" in target.read_text(encoding="utf-8")
    assert (sample.folder / "docs" / "doc-1.yaml").read_text(encoding="utf-8") == clone_text
    assert int(run_git(worktree, "rev-list", "--count", "HEAD")) == commits
    assert refused.is_error
    assert "SourceNotWritableError" in refused.text
    assert snapshot(notes.folder) == notes_before
    # S5: 変更をレビューする（エージェントが commit した 1 件が差分になる）
    run_git(worktree, "add", "-A")
    run_git(worktree, "commit", "-m", "docs: 改名")
    changed = run_git(worktree, "rev-parse", "HEAD").strip()
    changes = docs(
        "list_changes", source="sample", format="json", **{"from": parent, "to": changed}
    )
    diff = httpx.get(
        DOC_URL.format(port=port), params={"ref": changed, "diff": parent}, timeout=10
    ).json()
    assert int(run_git(worktree, "rev-list", "--count", "HEAD")) == commits + 1
    assert [(item["id"], item["change"], item["keys"]) for item in changes.data["items"]] == [
        ("doc-1", "modified", ["name"])
    ]
    assert "name" in diff["diff"]["changedItems"]
    # S6: 利用者が画面で読む
    page = httpx.get(LIST_URL.format(port=port), timeout=10).json()
    assert page["tabs"]
    assert "文書 1" in page["markdown"]
    # S7: YAML を直接編集した
    edited = sample_doc_text("doc-1", "直接編集した名前", description="1 件目", tags=["a"])
    target.write_text(edited, encoding="utf-8")
    reread = docs("search_docs", filter=DOC_1, view="full", format="json")
    item = reread.data["items"][0]["values"]
    assert "name: 直接編集した名前" in item["body"]
    assert item["version"] == content_hash(edited)
    assert item["version"] != read_version
    # S8: 設定・スクリプトを変える
    (sample.folder / "dev-docs.yaml").write_text(
        sample_config_text(description="書き換えた説明"), encoding="utf-8"
    )
    reloaded = admin("reload", format="json")
    assert not reloaded.is_error
    assert "書き換えた説明" in docs("describe").text
    # S9: dev-docs を更新する
    clone.push_upstream(clone.bump_version(NEW_VERSION), "bump")
    updated = update_server(port)
    after = wait_for_new_version(port, NEW_VERSION)
    assert updated.data["version"] == NEW_VERSION
    assert {s["id"] for s in after["sources"] if s["status"] == "serving"} == {"sample", "notes"}
    assert serve_pid_count(port) == 1
    assert sorted(list_mcp_tools(port)) == TOOL_NAMES
    assert claude_home.real_changes() == []


def test_error_when_source_config_invalid(
    make_clone: Callable[..., Any],
    make_source: Callable[..., Any],
    serve_from_clone: Callable[..., Any],
    write_files: Callable[[Path, dict[str, str]], None],
    sample_file_set: Callable[..., dict[str, str]],
    sample_config_text: Callable[..., str],
    list_mcp_tools: Callable[..., list[str]],
) -> None:
    """配信できない配信元があっても他の配信と管理の MCP は止まらず、直して `reload` で配信に入る（異常系）。"""
    # 準備
    clone = make_clone()
    sample = make_source("sample")
    broken = make_source(
        "broken", {"dev-docs.yaml": BROKEN_CONFIG}, git=False, scope_read=[sample.folder]
    )
    served = serve_from_clone(clone, sample, broken)
    cwd = {"cwd": str(sample.folder)}
    tools_before = list_mcp_tools(served.port)
    pid = served.call_admin("status", format="json").data["pid"]
    # 実行（起動の直後）
    broken_page = served.get("/_api/sources/broken/docs")
    sample_page = served.get("/_api/sources/sample/docs")
    not_served = served.call("search_docs", source="broken", format="json", **cwd)
    serving = served.call("search_docs", source="sample", view="ids", format="json", **cwd)
    status = served.call_admin("status", format="json").data
    # 実行（直して読み直す）
    write_files(
        broken.folder, sample_file_set(**{"dev-docs.yaml": sample_config_text(name="broken")})
    )
    reloaded = served.call_admin("reload", format="json")
    fixed = served.call("search_docs", source="broken", view="ids", format="json", **cwd)
    # 検証
    broken_state = next(row for row in status["sources"] if row["id"] == "broken")
    assert broken_page.status_code == 404
    assert sample_page.status_code == 200
    assert not_served.is_error
    assert "broken" in not_served.text
    assert [item["id"] for item in serving.data["items"]] == ["doc-1", "doc-2"]
    assert broken_state["status"] == "not_served"
    assert any("documents[0].paths" in error for error in broken_state["errors"])
    assert "broken: documents[0].paths: 必須のキーが無い" in served.stderr()
    assert not reloaded.is_error
    assert [item["id"] for item in fixed.data["items"]] == ["doc-1", "doc-2"]
    assert list_mcp_tools(served.port) == tools_before
    assert served.call_admin("status", format="json").data["pid"] == pid
