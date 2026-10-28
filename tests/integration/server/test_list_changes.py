from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from dev_docs.shared.hashing import content_hash

DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}
SHORT_SHA = 7


def _changed_source(
    make_source: Callable[..., Any],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    sample_doc_text: Callable[..., str],
    *,
    date: str | None = None,
) -> tuple[Any, str, str]:
    """文書 1 の name を変えた commit を持つ sample と、親の commit・変更の commit を返す。"""
    source = make_source("sample", date=date)
    parent = run_git(source.folder, "rev-parse", "HEAD").strip()
    renamed = sample_doc_text("doc-1", "新しい名前", description="1 件目", tags=["a"])
    changed = commit_all(
        source.folder, {"docs/doc-1.yaml": renamed}, "docs: 改名", date="2026-02-01T00:00:00+09:00"
    )
    return source, parent, changed


def test_normal(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    sample_doc_text: Callable[..., str],
) -> None:
    """2 つの commit の間に変わった文書とキー、差分の行を返す（正常系）。"""
    # 準備
    source, parent, changed = _changed_source(
        make_source, commit_all, run_git, sample_doc_text, date="2026-01-01T00:00:00+09:00"
    )
    env = make_server(source)
    arguments = {"cwd": str(source.folder), "source": "sample", "from": parent, "to": changed}
    # 実行
    summary = env.call("list_changes", format="json", **arguments)
    markdown = env.call("list_changes", **arguments)
    full = env.call("list_changes", view="full", format="json", **arguments)
    full_markdown = env.call("list_changes", view="full", **arguments)
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
    assert "path" not in full.data["items"][0]
    assert "scope" not in full.data["items"][0]
    assert "+ name: 新しい名前" in full_markdown.text
    assert "<document" not in full_markdown.text


def test_normal_when_range_by_date_and_branch(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    sample_doc_text: Callable[..., str],
) -> None:
    """日時とブランチ名を commit に解決して比べる（正常系）。"""
    # 準備
    source, parent, changed = _changed_source(
        make_source, commit_all, run_git, sample_doc_text, date="2026-01-01T00:00:00+09:00"
    )
    run_git(source.folder, "branch", "feat/range", changed)
    env = make_server(source)
    # 実行
    result = env.call(
        "list_changes",
        cwd=str(source.folder),
        source="sample",
        format="json",
        **{"from": "2026-01-15", "to": "feat/range"},
    )
    # 検証
    assert parent.startswith(result.data["range"]["from"]["commit"])
    assert changed.startswith(result.data["range"]["to"]["commit"])
    assert [(item["id"], item["keys"]) for item in result.data["items"]] == [("doc-1", ["name"])]


def test_normal_when_since_last_read(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
) -> None:
    """from を省き、この会話で前回読んだ内容と今の内容を比べる（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    worktree = add_worktree(sample.folder, "x")
    env = make_server(sample, notes)
    read = {"session_id": "s1", "view": "full"}
    env.call("search_docs", cwd=str(sample.folder), worktree=str(worktree), **read)
    env.call("search_docs", cwd=str(sample.folder), source="notes", **read)
    target = worktree / "docs" / "doc-1.yaml"
    env.call(
        "write_docs",
        cwd=str(sample.folder),
        worktree=str(worktree),
        operations=[
            {
                "op": "update",
                "id": "doc-1",
                "expected_version": content_hash(target.read_text(encoding="utf-8")),
                "set": {"name": "新しい名前"},
            }
        ],
    )
    notes_doc = notes.folder / "docs" / "doc-2.yaml"
    notes_doc.write_text("id: doc-2\nname: メモの新しい名前\n", encoding="utf-8")
    # 実行
    in_git = env.call(
        "list_changes",
        cwd=str(sample.folder),
        worktree=str(worktree),
        session_id="s1",
        format="json",
    )
    in_notes = env.call(
        "list_changes", cwd=str(sample.folder), source="notes", session_id="s1", format="json"
    )
    in_git_full = env.call(
        "list_changes",
        cwd=str(sample.folder),
        worktree=str(worktree),
        session_id="s1",
        view="full",
        format="json",
    )
    # 検証
    assert [(item["id"], item["keys"]) for item in in_git.data["items"]] == [("doc-1", ["name"])]
    assert in_git.data["items"][0]["path"] == f"{worktree}/docs/doc-1.yaml"
    assert in_git.data["items"][0]["scope"] == "summary"
    assert in_git_full.data["items"][0]["scope"] == "section"
    assert [item["id"] for item in in_notes.data["items"]] == ["doc-2"]


def test_error_when_ref_not_found(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """解決できない区間を断る（異常系）。"""
    # 準備
    source = make_source("sample")
    env = make_server(source)
    # 実行
    result = env.call(
        "list_changes", cwd=str(source.folder), source="sample", **{"from": "no-such-branch"}
    )
    # 検証
    assert result.is_error
    assert "RefNotFoundError" in result.text
    assert "no-such-branch" in result.text
    assert "from" in result.text


def test_error_when_last_read_not_found(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """読んだ記録の無い会話で from を省くと断る（異常系）。"""
    # 準備
    source = make_source("sample")
    env = make_server(source)
    # 実行
    result = env.call("list_changes", cwd=str(source.folder), session_id="s2")
    # 検証
    assert result.is_error
    assert "LastReadNotFoundError" in result.text
    assert "from" in result.text


def test_error_when_invalid_argument(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """Git 管理外の配信元への区間の指定と、from の無い to を断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    env = make_server(sample, notes)
    # 実行
    non_git = env.call("list_changes", cwd=str(sample.folder), source="notes", **{"from": "HEAD~1"})
    only_to = env.call("list_changes", cwd=str(sample.folder), source="sample", to="develop")
    # 検証
    assert non_git.is_error
    assert "InvalidArgumentError" in non_git.text
    assert "notes" in non_git.text
    assert only_to.is_error
    assert "InvalidArgumentError" in only_to.text
    assert "from" in only_to.text


def test_error_when_source_not_readable(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    commit_all: Callable[..., str],
    run_git: Callable[..., str],
    sample_doc_text: Callable[..., str],
) -> None:
    """scope に当たらない配信元の変更を返さない（異常系）。"""
    # 準備
    sample, parent, changed = _changed_source(make_source, commit_all, run_git, sample_doc_text)
    other = make_source("other")
    env = make_server(sample, other)
    # 実行
    single = env.call(
        "list_changes", cwd=str(sample.folder), source="other", **{"from": parent, "to": changed}
    )
    everything = env.call(
        "list_changes",
        cwd=str(sample.folder),
        source="*",
        format="json",
        **{"from": parent, "to": changed},
    )
    # 検証
    assert single.is_error
    assert "SourceNotReadableError" in single.text
    assert "other" in single.text
    assert "sample" in single.text
    assert not everything.is_error
    assert "other" not in everything.text
