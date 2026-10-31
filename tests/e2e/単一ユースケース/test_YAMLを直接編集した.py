from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dev_docs.shared.hashing import content_hash
from dev_docs.shared.yaml_io import load_yaml

DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}
SEEN = "（この会話で返し済み）"
DOC_URL = "/_api/sources/sample/docs/docs/doc-1"


def _setup(
    make_source: Callable[..., Any], serve: Callable[..., Any], add_worktree: Callable[..., Path]
) -> tuple[Any, Any, Path]:
    """ワークツリー x を持つ sample を配信し、配信元・起動したサーバー・ワークツリーを返す。"""
    source = make_source("sample")
    worktree = add_worktree(source.folder, "x")
    return source, serve(source), worktree


def _read_full(served: Any, source: Any, worktree: Path, session_id: str) -> Any:
    """文書 1 を view: full で読む。"""
    return served.call(
        "search_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        session_id=session_id,
        filter=DOC_1,
        view="full",
        format="json",
    )


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
    commit_all: Callable[..., str],
) -> None:
    """直接編集した後の取得が、読み直した内容と新しいバージョンを返す（正常系）。"""
    # 準備
    source, served, worktree = _setup(make_source, serve, add_worktree)
    first = _read_full(served, source, worktree, "s1")
    read_version = first.data["items"][0]["values"]["version"]
    edited = sample_doc_text("doc-1", "直接編集した名前", description="1 件目", tags=["a"])
    # 実行
    (worktree / "docs" / "doc-1.yaml").write_text(edited, encoding="utf-8")
    commit_all(source.folder, {"docs/doc-1.yaml": edited}, "docs: 直接編集")
    second = _read_full(served, source, worktree, "s1")
    document = served.get(DOC_URL)
    # 検証
    item = second.data["items"][0]["values"]
    assert "name: 直接編集した名前" in item["body"]
    assert SEEN not in item["body"]
    assert item["version"] == content_hash(edited)
    assert item["version"] != read_version
    assert document.status_code == 200
    assert "直接編集した名前" in document.json()["markdown"]


def test_error_when_version_mismatch(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
) -> None:
    """読んだときのバージョンでは、直接編集した内容を上書きしない（異常系）。"""
    # 準備
    source, served, worktree = _setup(make_source, serve, add_worktree)
    target = worktree / "docs" / "doc-1.yaml"
    first = _read_full(served, source, worktree, "s1")
    read_version = first.data["items"][0]["values"]["version"]
    edited = sample_doc_text("doc-1", "文書 1", description="直接編集した概要文", tags=["a"])
    target.write_text(edited, encoding="utf-8")
    arguments = {"cwd": str(source.folder), "worktree": str(worktree), "session_id": "s1"}
    update = {"op": "update", "id": "doc-1", "set": {"name": "新しい名前"}}
    # 実行
    mismatch = served.call(
        "write_docs", operations=[{**update, "expected_version": read_version}], **arguments
    )
    after_mismatch = target.read_text(encoding="utf-8")
    deleted = served.call(
        "delete_docs", targets=[{"id": "doc-1", "expected_version": read_version}], **arguments
    )
    reread = _read_full(served, source, worktree, "s1")
    retried = served.call(
        "write_docs",
        operations=[{**update, "expected_version": reread.data["items"][0]["values"]["version"]}],
        **arguments,
    )
    # 検証
    written = load_yaml(target.read_text(encoding="utf-8"))
    assert mismatch.is_error
    assert "VersionMismatchError" in mismatch.text
    assert content_hash(edited) in mismatch.text
    assert "直接編集した概要文" in mismatch.text
    assert after_mismatch == edited
    assert deleted.is_error
    assert "VersionMismatchError" in deleted.text
    assert reread.data["items"][0]["values"]["version"] == content_hash(edited)
    assert retried.data["results"][0]["status"] == "updated"
    assert written["name"] == "新しい名前"
    assert written["description"] == "直接編集した概要文"


def test_error_when_yaml_broken(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    commit_all: Callable[..., str],
) -> None:
    """YAML として読めなくなった文書を除き、読めなかった理由を返す（異常系）。"""
    # 準備
    source, served, worktree = _setup(make_source, serve, add_worktree)
    (worktree / "docs" / "doc-1.yaml").write_text("a: [1\n", encoding="utf-8")
    commit_all(source.folder, {"docs/doc-1.yaml": "a: [1\n"}, "docs: 壊す")
    # 実行
    result = served.call(
        "search_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        view="summary",
        format="json",
    )
    document = served.get(DOC_URL)
    # 検証
    notes = " ".join(result.data["notes"])
    broken = document.json()["conversionError"]
    assert [item["id"] for item in result.data["items"]] == ["doc-2"]
    assert "docs/doc-1.yaml" in notes
    assert re.search(r"1.*\d+", notes)
    assert document.status_code == 200
    assert document.json()["markdown"] is None
    assert broken["reason"] == "invalid_yaml"
    assert broken["file"] == "docs/doc-1.yaml"
    assert broken["line"] >= 1
    assert broken["column"] >= 1
