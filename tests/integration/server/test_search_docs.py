from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

BROKEN_CONFIG = "name: broken\ndocuments:\n  - id: sample\n    type: yaml\n"
BY_ID = {"field": "id", "op": "eq", "values": ["doc-2", "doc-1"]}
DOC_1 = {"field": "id", "op": "eq", "values": ["doc-1"]}


def test_normal(make_source: Callable[..., Any], make_server: Callable[..., Any]) -> None:
    """source を省いて作業中の配信元の一覧を返す（正常系）。"""
    # 準備
    source = make_source("sample")
    env = make_server(source)
    # 実行
    result = env.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "kind", "op": "eq", "values": ["sample"]},
        view="summary",
    )
    # 検証
    rows = [line for line in result.text.splitlines() if line.startswith("| doc-")]
    assert not result.is_error
    assert result.text.startswith("sample: 該当 2 件・返した 2 件")
    assert [row.split("|")[1].strip() for row in rows] == ["doc-1", "doc-2"]
    assert all(re.search(r"\| [0-9a-f]{6} \|$", row) for row in rows)
    assert result.structured is None


def test_normal_when_full(make_source: Callable[..., Any], make_server: Callable[..., Any]) -> None:
    """ID で絞って view: full で本文を返す（正常系）。"""
    # 準備
    source = make_source("sample")
    env = make_server(source)
    # 実行
    markdown = env.call("search_docs", cwd=str(source.folder), filter=BY_ID, view="full")
    as_json = env.call(
        "search_docs", cwd=str(source.folder), filter=BY_ID, view="full", format="json"
    )
    # 検証
    documents = re.findall(r"<document[^>]*>(.*?)</document>", markdown.text, flags=re.S)
    assert len(documents) == 2
    assert "id: doc-2" in documents[0]
    assert "id: doc-1" in documents[1]
    assert as_json.structured is not None
    assert as_json.structured == as_json.data
    assert [item["id"] for item in as_json.data["items"]] == ["doc-2", "doc-1"]
    assert "id: doc-2" in as_json.data["items"][0]["values"]["body"]


def test_normal_when_count_grouped(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """view: count と group_by で件数と値ごとの件数だけを返す（正常系）。"""
    # 準備
    source = make_source("sample")
    env = make_server(source)
    # 実行
    result = env.call(
        "search_docs", cwd=str(source.folder), view="count", group_by="tags", format="json"
    )
    # 検証
    assert result.data["total_count"] == 2
    assert result.data["groups"] == [{"value": "a", "count": 2}, {"value": "b", "count": 1}]
    assert not result.data.get("items")


def test_normal_when_ordered_and_limited(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
    sample_doc_text: Callable[..., str],
    commit_all: Callable[..., str],
) -> None:
    """order_by の複数キーで並べ、limit を丸め、max_chars で打ち切る（正常系）。"""
    # 準備
    older = {
        f"docs/a-{n:03d}.yaml": sample_doc_text(f"a-{n:03d}", "旧", description="x" * (100 + n))
        for n in range(1, 61)
    }
    newer = {
        f"docs/b-{n:03d}.yaml": sample_doc_text(f"b-{n:03d}", "新", description="x" * (100 + n))
        for n in range(1, 61)
    }
    files = sample_file_set(**older)
    del files["docs/doc-1.yaml"], files["docs/doc-2.yaml"]
    source = make_source("sample", files, date="2026-01-01T00:00:00+09:00")
    commit_all(source.folder, newer, "docs: 新しい文書", date="2026-02-01T00:00:00+09:00")
    env = make_server(source)
    arguments = {
        "cwd": str(source.folder),
        "order_by": [
            {"field": "updated", "direction": "desc"},
            {"field": "@chars", "direction": "asc"},
        ],
        "format": "json",
    }
    # 実行
    first = env.call("search_docs", limit=150, **arguments)
    second = env.call("search_docs", limit=150, max_chars=500, **arguments)
    third = env.call(
        "search_docs",
        limit=150,
        max_chars=500,
        cursor=second.data["next_cursor"],
        **arguments,
    )
    # 検証
    ids = [item["id"] for item in first.data["items"]]
    assert len(ids) == 100
    assert (ids[0], ids[59], ids[60], ids[99]) == ("b-001", "b-060", "a-001", "a-040")
    assert any("100" in note for note in first.data["notes"])
    assert first.data["next_cursor"]
    assert second.data["truncated"] is True
    assert second.data["next_cursor"]
    assert any("view: ids" in note for note in second.data["notes"])
    second_ids = [item["id"] for item in second.data["items"]]
    third_ids = [item["id"] for item in third.data["items"]]
    assert third_ids
    assert set(second_ids).isdisjoint(third_ids)


def test_normal_when_source_all(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """source: * で読める全配信元を横断する（正常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    other = make_source("other", scope_read=[Path("/nonexistent-other")])
    env = make_server(sample, notes, other)
    # 実行
    result = env.call("search_docs", cwd=str(sample.folder), source="*", format="json")
    # 検証
    sources = {item["source"] for item in result.data["items"]}
    assert not result.is_error
    assert sources == {"sample", "notes"}
    assert result.data["per_source"] == {"sample": 2, "notes": 2}


def test_normal_when_worktree(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    add_worktree: Callable[..., Path],
    sample_doc_text: Callable[..., str],
) -> None:
    """worktree か cwd で指したワークツリーの文書を返す（正常系）。"""
    # 準備
    source = make_source("sample")
    worktree = add_worktree(source.folder, "x")
    (worktree / "docs" / "doc-1.yaml").write_text(
        sample_doc_text("doc-1", "ワークツリーの名前"), encoding="utf-8"
    )
    env = make_server(source)
    arguments = {"filter": DOC_1, "view": "full"}
    # 実行
    by_worktree = env.call(
        "search_docs", cwd=str(source.folder), worktree=str(worktree), **arguments
    )
    by_cwd = env.call("search_docs", cwd=str(worktree), **arguments)
    by_clone = env.call("search_docs", cwd=str(source.folder), **arguments)
    # 検証
    assert "name: ワークツリーの名前" in by_worktree.text
    assert "name: ワークツリーの名前" in by_cwd.text
    assert "name: 文書 1" in by_clone.text
    assert "ワークツリーの名前" not in by_clone.text


def test_normal_when_seen(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_doc_text: Callable[..., str],
) -> None:
    """同じ会話で同じバージョンの本文を 2 回目は省く（正常系）。"""
    # 準備
    source = make_source("sample")
    env = make_server(source)
    arguments = {"cwd": str(source.folder), "filter": DOC_1, "view": "full"}
    body = "id: doc-1\nname: 文書 1"
    # 実行
    first = env.call("search_docs", session_id="s1", **arguments)
    second = env.call("search_docs", session_id="s1", **arguments)
    repeated = env.call("search_docs", session_id="s1", repeat_seen=True, **arguments)
    other_session = env.call("search_docs", session_id="s2", **arguments)
    summary = env.call(
        "search_docs", cwd=str(source.folder), session_id="s1", filter=DOC_1, view="summary"
    )
    (source.folder / "docs" / "doc-1.yaml").write_text(
        sample_doc_text("doc-1", "変更後の名前"), encoding="utf-8"
    )
    changed = env.call("search_docs", session_id="s1", **arguments)
    # 検証
    assert body in first.text
    assert "（この会話で返し済み）" in second.text
    assert body not in second.text
    assert body in repeated.text
    assert body in other_session.text
    assert "1 件目" in summary.text
    assert "id: doc-1\nname: 変更後の名前" in changed.text


def test_normal_when_file_unreadable(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """YAML として読めないファイルを除いて返し、notes で知らせる（正常系）。"""
    # 準備
    source = make_source("sample")
    (source.folder / "docs" / "doc-1.yaml").write_text("a: [1\n", encoding="utf-8")
    env = make_server(source)
    # 実行
    result = env.call("search_docs", cwd=str(source.folder), view="summary", format="json")
    # 検証
    notes = " ".join(result.data["notes"])
    assert not result.is_error
    assert [item["id"] for item in result.data["items"]] == ["doc-2"]
    assert "docs/doc-1.yaml" in notes
    assert re.search(r"1.*\d+", notes)


def test_error_when_source_not_readable(
    make_source: Callable[..., Any],
    make_server: Callable[..., Any],
    sample_file_set: Callable[..., dict[str, str]],
) -> None:
    """scope.read に当たらない配信元を指すと断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    other_files = sample_file_set(**{"docs/doc-1.yaml": "id: secret-1\nname: 秘密\n"})
    other = make_source("other", other_files)
    env = make_server(sample, other)
    # 実行
    with_cwd = env.call("search_docs", cwd=str(sample.folder), source="other")
    without_cwd = env.call("search_docs", source="other")
    # 検証
    for result in (with_cwd, without_cwd):
        assert result.is_error
        assert "other" in result.text
        assert "SourceNotReadableError" in result.text
        assert "secret-1" not in result.text
    assert "sample" in with_cwd.text


def test_error_when_source_not_served(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """起動時の検証で外した配信元を指すと、外した理由を返す（異常系）。"""
    # 準備
    sample = make_source("sample")
    broken = make_source("broken", {"dev-docs.yaml": BROKEN_CONFIG}, scope_read=[sample.folder])
    env = make_server(sample, broken)
    # 実行
    result = env.call("search_docs", cwd=str(sample.folder), source="broken")
    # 検証
    assert result.is_error
    assert "SourceNotServedError" in result.text
    assert "broken" in result.text
    assert "documents[0].paths" in result.text


def test_error_when_worktree_not_matched(
    make_source: Callable[..., Any], make_server: Callable[..., Any], tmp_path: Path
) -> None:
    """worktrees に当たらない worktree を断る（異常系）。"""
    # 準備
    source = make_source("sample")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    env = make_server(source)
    # 実行
    result = env.call("search_docs", cwd=str(source.folder), worktree=str(elsewhere))
    # 検証
    assert result.is_error
    assert "WorktreeNotMatchedError" in result.text
    assert str(elsewhere) in result.text
    assert ".claude/worktrees" in result.text


def test_error_when_invalid_argument(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """スキーマに無い項目や型の合わない値を、直し方を添えて断る（異常系）。"""
    # 準備
    source = make_source("sample")
    env = make_server(source)
    # 実行
    unknown_field = env.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "nme", "op": "eq", "values": ["x"]},
    )
    bad_value = env.call(
        "search_docs",
        cwd=str(source.folder),
        filter={"field": "weight", "op": "gt", "values": ["abc"]},
    )
    # 検証
    assert unknown_field.is_error
    assert "InvalidArgumentError" in unknown_field.text
    assert "filter.field" in unknown_field.text
    assert "nme" in unknown_field.text
    assert "describe" in unknown_field.text
    assert bad_value.is_error
    assert "abc" in bad_value.text
    assert "number" in bad_value.text


def test_error_when_ref_not_found(
    make_source: Callable[..., Any], make_server: Callable[..., Any]
) -> None:
    """解決できない ref を断る（異常系）。"""
    # 準備
    sample = make_source("sample")
    notes = make_source("notes", git=False, scope_read=[sample.folder])
    env = make_server(sample, notes)
    # 実行
    no_ref = env.call("search_docs", cwd=str(sample.folder), ref="no-such-branch")
    non_git = env.call("search_docs", cwd=str(sample.folder), source="notes", ref="develop")
    # 検証
    assert no_ref.is_error
    assert "RefNotFoundError" in no_ref.text
    assert "no-such-branch" in no_ref.text
    assert non_git.is_error
    assert "ref" in non_git.text
