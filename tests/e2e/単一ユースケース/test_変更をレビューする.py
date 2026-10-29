from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from dev_docs.shared.hashing import content_hash

SHORT_SHA = 7
PARENT_DATE = "2026-01-01T00:00:00+09:00"
CHANGED_DATE = "2026-02-01T00:00:00+09:00"
BOTH_DOCS = {"field": "kind", "op": "eq", "values": ["sample"]}
WORD = "廃止予定"


def _version(path: Path) -> str:
    """文書のファイルの今のバージョン（内容のハッシュ）を返す。"""
    return content_hash(path.read_text(encoding="utf-8"))


def _rename_doc_1(served: Any, source: Any, worktree: Path, *, name: str) -> None:
    """ワークツリーの文書 1 の name を `write_docs` で変える。"""
    target = worktree / "docs" / "doc-1.yaml"
    result = served.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[
            {
                "op": "update",
                "id": "doc-1",
                "expected_version": _version(target),
                "set": {"name": name},
            }
        ],
    )
    assert not result.is_error


def _set_and_commit(
    served: Any,
    source: Any,
    worktree: Path,
    run_git: Callable[..., str],
    doc_id: str,
    fields: dict[str, str],
) -> str:
    """ワークツリーの文書の項目を `write_docs` で変えて commit し、その commit を返す。"""
    target = worktree / "docs" / f"{doc_id}.yaml"
    result = served.call(
        "write_docs",
        cwd=str(source.folder),
        worktree=str(worktree),
        operations=[
            {"op": "update", "id": doc_id, "expected_version": _version(target), "set": fields}
        ],
    )
    assert not result.is_error
    run_git(worktree, "add", "-A")
    run_git(worktree, "commit", "-m", f"docs: {doc_id} を変える")
    return run_git(worktree, "rev-parse", "HEAD").strip()


def _changed_range(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
) -> tuple[Any, Any, str, str]:
    """文書 1 の name を変えて commit した sample と、親の commit・変更の commit を返す。"""
    source = make_source("sample", date=PARENT_DATE)
    worktree = add_worktree(source.folder, "x")
    served = serve(source)
    parent = run_git(worktree, "rev-parse", "HEAD").strip()
    _rename_doc_1(served, source, worktree, name="新しい名前")
    run_git(worktree, "add", "-A")
    run_git(
        worktree,
        "commit",
        "-m",
        "docs: 改名",
        env={"GIT_AUTHOR_DATE": CHANGED_DATE, "GIT_COMMITTER_DATE": CHANGED_DATE},
    )
    changed = run_git(worktree, "rev-parse", "HEAD").strip()
    return source, served, parent, changed


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
) -> None:
    """2 つの commit の間に変わった文書とキー、差分の行を返す（正常系）。"""
    # 準備
    source, served, parent, changed = _changed_range(make_source, serve, add_worktree, run_git)
    arguments = {"cwd": str(source.folder), "source": "sample", "from": parent, "to": changed}
    # 実行
    summary = served.call("list_changes", format="json", **arguments)
    markdown = served.call("list_changes", **arguments)
    full = served.call("list_changes", view="full", format="json", **arguments)
    # 検証
    items = summary.data["items"]
    assert parent.startswith(summary.data["range"]["from"]["commit"])
    assert changed.startswith(summary.data["range"]["to"]["commit"])
    assert [(item["id"], item["change"], item["keys"]) for item in items] == [
        ("doc-1", "modified", ["name"])
    ]
    assert parent[:SHORT_SHA] in markdown.text
    assert changed[:SHORT_SHA] in markdown.text
    assert "- name: 文書 1" in full.data["items"][0]["diff"]
    assert "+ name: 新しい名前" in full.data["items"][0]["diff"]


def test_normal_when_range_by_date_and_branch(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
) -> None:
    """日時とブランチ名を commit に解決して比べる（正常系）。"""
    # 準備
    source, served, parent, changed = _changed_range(make_source, serve, add_worktree, run_git)
    # 実行
    result = served.call(
        "list_changes",
        cwd=str(source.folder),
        source="sample",
        format="json",
        **{"from": "2026-01-15", "to": "feat/x"},
    )
    # 検証
    assert parent.startswith(result.data["range"]["from"]["commit"])
    assert changed.startswith(result.data["range"]["to"]["commit"])
    assert [(item["id"], item["keys"]) for item in result.data["items"]] == [("doc-1", ["name"])]


def test_normal_when_since_last_read(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
) -> None:
    """from を省き、この会話で前回読んだ時点から今までを比べる（正常系）。"""
    # 準備
    source = make_source("sample")
    worktree = add_worktree(source.folder, "x")
    served = serve(source)
    arguments = {"cwd": str(source.folder), "worktree": str(worktree)}
    served.call("search_docs", filter=BOTH_DOCS, view="full", session_id="s1", **arguments)
    _rename_doc_1(served, source, worktree, name="新しい名前")
    # 実行
    result = served.call("list_changes", session_id="s1", format="json", **arguments)
    other_session = served.call("list_changes", session_id="s2", **arguments)
    # 検証
    assert [(item["id"], item["keys"]) for item in result.data["items"]] == [("doc-1", ["name"])]
    assert other_session.is_error
    assert "LastReadNotFoundError" in other_session.text
    assert "from" in other_session.text


def test_error_when_ref_not_found(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """解決できない区間を断り、差分を返さない（異常系）。"""
    # 準備
    source = make_source("sample")
    served = serve(source)
    # 実行
    result = served.call(
        "list_changes", cwd=str(source.folder), source="sample", **{"from": "no-such-branch"}
    )
    # 検証
    assert result.is_error
    assert "RefNotFoundError" in result.text
    assert "no-such-branch" in result.text
    assert "from" in result.text
    assert "doc-1" not in result.text


def test_normal_when_contains(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    run_git: Callable[..., str],
) -> None:
    """語が入った・消えた変更を引く（正常系）。"""
    # 準備
    source = make_source("sample")
    worktree = add_worktree(source.folder, "x")
    served = serve(source)
    parent = run_git(worktree, "rev-parse", "HEAD").strip()
    added = _set_and_commit(served, source, worktree, run_git, "doc-1", {"description": WORD})
    middle = _set_and_commit(served, source, worktree, run_git, "doc-2", {"name": "文書 2 改"})
    removed = _set_and_commit(served, source, worktree, run_git, "doc-1", {"description": "1 件目"})
    arguments = {
        "cwd": str(source.folder),
        "source": "sample",
        "from": parent,
        "to": removed,
        "format": "json",
    }
    # 実行
    result = served.call("list_changes", contains={"value": WORD}, **arguments)
    without_contains = served.call("list_changes", **arguments)
    # 検証
    changes = result.data["items"][0]["contains_changes"]
    assert [item["id"] for item in result.data["items"]] == ["doc-1"]
    assert [
        (change["kind"], change["from"]["commit"], change["to"]["commit"]) for change in changes
    ] == [
        ("added", parent[:SHORT_SHA], added[:SHORT_SHA]),
        ("removed", middle[:SHORT_SHA], removed[:SHORT_SHA]),
    ]
    assert [item["id"] for item in without_contains.data["items"]] == ["doc-2"]
