from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    type: yaml\n"
DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}
SEEN = "（この会話で返し済み）"


def _related_files(
    sample_file_set: Callable[..., dict[str, str]], sample_doc_text: Callable[..., str]
) -> dict[str, str]:
    """文書 1 の related が文書 2 を指す、配信元のファイル一式を返す。"""
    return sample_file_set(
        **{
            "docs/doc-1.yaml": sample_doc_text(
                "doc-1",
                "文書 1",
                description="1 件目",
                related=[{"to": "doc-2", "type": "references"}],
            )
        }
    )


def test_normal(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """使える配信元・種類・文書を順に絞って読む（正常系）。"""
    # 準備
    sample = make_source("sample", _related_files(sample_file_set, sample_doc_text))
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    served = serve(sample, notes)
    arguments = {"cwd": str(sample.folder)}
    # 実行
    sources = served.call("describe", **arguments)
    detail = served.call("describe", source="sample", **arguments)
    summary = served.call(
        "search_docs",
        filter={"field": "kind", "op": "eq", "values": ["sample"]},
        view="summary",
        **arguments,
    )
    full = served.call("search_docs", filter=DOC_1, view="full", **arguments)
    related = served.call("trace_related", from_ids=["doc-1"], format="json", **arguments)
    # 検証
    rows = [line for line in summary.text.splitlines() if line.startswith("| doc-")]
    assert "| sample | write（作業中） |" in sources.text
    assert "| notes | read |" in sources.text
    assert "| sample |" in detail.text
    assert summary.text.startswith("sample: 該当 2 件・返した 2 件")
    assert [row.split("|")[1].strip() for row in rows] == ["doc-1", "doc-2"]
    assert all(re.search(r"\| [0-9a-f]{6} \|$", row) for row in rows)
    assert "id: doc-1" in full.text
    assert "name: 文書 1" in full.text
    assert [item["id"] for item in related.data["items"]] == ["doc-2"]


def test_normal_when_source_all(make_source: Callable[..., Any], serve: Callable[..., Any]) -> None:
    """scope.read に当たる全ての配信元を横断する（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    served = serve(sample, notes)
    # 実行
    everything = served.call("search_docs", cwd=str(sample.folder), source="*", format="json")
    only_sample = served.call(
        "search_docs", cwd=str(sample.folder), source=["sample"], format="json"
    )
    # 検証
    assert {item["source"] for item in everything.data["items"]} == {"sample", "notes"}
    assert everything.data["per_source"] == {"sample": 2, "notes": 2}
    assert [item["id"] for item in only_sample.data["items"]] == ["doc-1", "doc-2"]
    assert "notes" not in only_sample.text


def test_normal_when_worktree_given(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
) -> None:
    """worktree か、ワークツリーの中の cwd で指したワークツリーの文書を読む（正常系）。"""
    # 準備
    sample = make_source("sample")
    worktree = add_worktree(sample.folder, "x")
    (worktree / "docs" / "doc-1.yaml").write_text(
        sample_doc_text("doc-1", "ワークツリーの名前"), encoding="utf-8"
    )
    served = serve(sample)
    arguments = {"filter": DOC_1, "view": "full"}
    # 実行
    by_worktree = served.call(
        "search_docs", cwd=str(sample.folder), worktree=str(worktree), **arguments
    )
    by_cwd = served.call("search_docs", cwd=str(worktree), **arguments)
    by_clone = served.call("search_docs", cwd=str(sample.folder), **arguments)
    # 検証
    assert "name: ワークツリーの名前" in by_worktree.text
    assert "name: ワークツリーの名前" in by_cwd.text
    assert "name: 文書 1" in by_clone.text
    assert "ワークツリーの名前" not in by_clone.text


def test_normal_when_same_doc_twice(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
) -> None:
    """同じ会話で同じバージョンの本文を 2 回目は省く（正常系）。"""
    # 準備
    sample = make_source("sample", _related_files(sample_file_set, sample_doc_text))
    served = serve(sample)
    full = {"cwd": str(sample.folder), "filter": DOC_1, "view": "full"}
    related = {"cwd": str(sample.folder), "from_ids": ["doc-1"], "format": "json"}
    summary = {"cwd": str(sample.folder), "view": "summary"}
    body = "id: doc-1\nname: 文書 1"
    # 実行
    first = served.call("search_docs", session_id="s1", **full)
    second = served.call("search_docs", session_id="s1", **full)
    repeated = served.call("search_docs", session_id="s1", repeat_seen=True, **full)
    other_session = served.call("search_docs", session_id="s2", **full)
    first_related = served.call("trace_related", session_id="s3", **related)
    second_related = served.call("trace_related", session_id="s3", **related)
    served.call("search_docs", session_id="s1", **summary)
    second_summary = served.call("search_docs", session_id="s1", **summary)
    # 検証
    assert body in first.text
    assert SEEN in second.text
    assert body not in second.text
    assert body in repeated.text
    assert body in other_session.text
    assert first_related.data["items"][0]["name"] == "文書 2"
    assert second_related.data["items"][0]["name"] == SEEN
    assert second_related.data["items"][0]["description"] == SEEN
    assert "1 件目" in second_summary.text


def test_error_when_source_not_readable(
    make_source: Callable[..., Any],
    serve: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """scope.read に当たらない配信元を指すと、使える配信元の一覧を返して文書は返さない（異常系）。"""
    # 準備
    sample = make_source("sample")
    other_files = sample_file_set(**{"docs/doc-1.yaml": "id: secret-1\nname: 秘密\n"})
    other = make_source("other", other_files)
    served = serve(sample, other)
    # 実行
    with_cwd = served.call("search_docs", cwd=str(sample.folder), source="other")
    without_cwd = served.call("search_docs", source="other")
    everything = served.call("search_docs", cwd=str(sample.folder), source="*", format="json")
    # 検証
    for result in (with_cwd, without_cwd):
        assert result.is_error
        assert "SourceNotReadableError" in result.text
        assert "other" in result.text
        assert "secret-1" not in result.text
    assert "sample" in with_cwd.text
    assert [item["id"] for item in everything.data["items"]] == ["doc-1", "doc-2"]
    assert "other" not in everything.text
    assert "secret-1" not in everything.text


def test_error_when_source_not_served(
    make_source: Callable[..., Any], serve: Callable[..., Any]
) -> None:
    """起動時の検証で外した配信元を指すと、違反を返す（異常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, scope_read=[sample.folder])
    served = serve(sample, broken)
    # 実行
    result = served.call("search_docs", cwd=str(sample.folder), source="broken")
    other = served.call("search_docs", cwd=str(sample.folder), source="sample", format="json")
    # 検証
    assert result.is_error
    assert "SourceNotServedError" in result.text
    assert "broken" in result.text
    assert "documents[0].paths" in result.text
    assert [item["id"] for item in other.data["items"]] == ["doc-1", "doc-2"]


def test_error_when_worktree_not_matched(
    make_source: Callable[..., Any], serve: Callable[..., Any], tmp_path: Path
) -> None:
    """worktrees に当たらないパスを指すと、パスと worktrees の値を返す（異常系）。"""
    # 準備
    sample = make_source("sample")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    served = serve(sample)
    # 実行
    result = served.call("search_docs", cwd=str(sample.folder), worktree=str(elsewhere))
    # 検証
    assert result.is_error
    assert "WorktreeNotMatchedError" in result.text
    assert str(elsewhere) in result.text
    assert ".claude/worktrees" in result.text
    assert "doc-1" not in result.text
