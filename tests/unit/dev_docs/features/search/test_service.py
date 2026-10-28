from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.search.service import search_docs
from dev_docs.features.search.types import (
    SUMMARY_FIELDS,
    Condition,
    GroupCount,
    OrderKey,
    SearchRequest,
    SearchResult,
    Snippet,
    SnippetLine,
    Snippets,
)
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.seen.types import SEEN_MARK
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import (
    DocumentTable,
    ScriptEntry,
    ServedSource,
    SourceConfig,
)
from dev_docs.features.validation.service import DocumentChecker
from dev_docs.shared.errors import InvalidArgumentError

TODAY = date(2026, 10, 28)


@dataclass
class SearchEnv:
    """検索に渡す部品と、作業場所に当たる配信元のフォルダ。"""

    registry: SourceRegistry
    store: DocumentStore
    checker: DocumentChecker
    seen: SeenStore
    root: Path

    def search(self, **request: Any) -> SearchResult:
        return search_docs(
            SearchRequest(cwd=str(self.root), **request),
            registry=self.registry,
            store=self.store,
            checker=self.checker,
            seen=self.seen,
            today=TODAY,
        )


@pytest.fixture
def make_env(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> Callable[..., SearchEnv]:
    """文書のファイルを置いた配信元 sample と、検索に渡す部品を作る関数を返す。"""

    def _make(
        files: dict[str, str],
        *,
        validators: list[ScriptEntry] | None = None,
        row_validators: list[str] | None = None,
        extra_sources: list[ServedSource] | None = None,
    ) -> SearchEnv:
        root = tmp_path / "sample"
        write_files(root, files)
        table = DocumentTable(
            id="rules",
            type="yaml",
            paths=["docs/*.yaml"],
            validators=row_validators or [],
        )
        config = make_source_config(documents=[table], validators=validators or [])
        source = make_served_source(id="sample", root=root, config=config)
        store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
        checker = DocumentChecker(store, timeout_sec=10)
        seen = SeenStore(tmp_path / "seen.sqlite3", retention_days=7)
        registry = make_registry(source, *(extra_sources or []))
        return SearchEnv(registry, store, checker, seen, root)

    return _make


TWO_DOCS = {
    "docs/doc-1.yaml": "id: doc-1\nname: 文書 1\ndescription: 1 件目\n",
    "docs/doc-2.yaml": "id: doc-2\nname: 文書 2\ndescription: 2 件目\n",
}


def test_search_docs(make_env: Callable[..., SearchEnv]) -> None:
    """作業中の配信元の一覧（正常系）。"""
    # 準備
    env = make_env(TWO_DOCS)
    # 実行
    result = env.search()
    # 検証
    assert result.total_count == 2
    assert [item.id for item in result.items] == ["doc-1", "doc-2"]
    assert list(result.items[0].values) == list(SUMMARY_FIELDS)


def test_search_docs_when_full_and_seen(make_env: Callable[..., SearchEnv]) -> None:
    """本文と返し済み（正常系）。"""
    # 準備
    env = make_env(TWO_DOCS)
    condition = Condition(field="id", op="eq", values=["doc-1"])
    body = TWO_DOCS["docs/doc-1.yaml"]
    # 実行
    first = env.search(filter=condition, view="full", session_id="s1")
    second = env.search(filter=condition, view="full", session_id="s1")
    third = env.search(filter=condition, view="full", session_id="s1", repeat_seen=True)
    # 検証
    assert first.items[0].values["body"] == body
    assert first.items[0].scope == "full"
    assert second.items[0].values["body"] == SEEN_MARK
    assert second.items[0].path is None
    assert second.items[0].scope is None
    assert third.items[0].values["body"] == body
    assert third.items[0].scope == "full"


def test_search_docs_when_count_grouped(make_env: Callable[..., SearchEnv]) -> None:
    """件数と集計（正常系）。"""
    # 準備
    env = make_env(
        {
            "docs/doc-1.yaml": "id: doc-1\nname: 1\ntags: [a, b]\n",
            "docs/doc-2.yaml": "id: doc-2\nname: 2\ntags: [a]\n",
            "docs/doc-3.yaml": "id: doc-3\nname: 3\n",
        }
    )
    # 実行
    result = env.search(view="count", group_by="tags")
    # 検証
    assert result.items == []
    assert result.groups == [
        GroupCount(value="a", count=2),
        GroupCount(value="b", count=1),
        GroupCount(value="（なし）", count=1),
    ]


def test_search_docs_when_limited(make_env: Callable[..., SearchEnv]) -> None:
    """上限と打ち切りと続き（正常系）。"""
    # 準備
    files = {
        f"docs/doc-{number}.yaml": f"id: doc-{number}\nname: n\ntext: {'x' * 9000}\n"
        for number in range(1, 6)
    }
    env = make_env(files)
    request = {"view": "full", "limit": 150, "max_chars": 20000}
    # 実行
    first = env.search(**request)
    second = env.search(**request, cursor=first.next_cursor)
    # 検証
    assert any("100" in note for note in first.notes)
    assert first.returned == 2
    assert first.truncated is True
    assert first.next_cursor is not None
    assert [item.id for item in second.items] == ["doc-3", "doc-4"]


def test_search_docs_when_order_by_dates(make_env: Callable[..., SearchEnv]) -> None:
    """日時の空は末尾（正常系）。"""
    # 準備
    env = make_env(
        {
            "docs/doc-1.yaml": "id: doc-1\nname: 1\nupdated: 2026-10-01T00:00:00+00:00\n",
            "docs/doc-2.yaml": "id: doc-2\nname: 2\n",
            "docs/doc-3.yaml": "id: doc-3\nname: 3\nupdated: 2026-10-05T00:00:00+00:00\n",
        }
    )
    # 実行
    result = env.search(order_by=[OrderKey(field="updated", direction="desc")])
    # 検証
    assert [item.id for item in result.items] == ["doc-3", "doc-1", "doc-2"]


def test_search_docs_when_snippets_regex(make_env: Callable[..., SearchEnv]) -> None:
    """正規表現で当てた文書の抜粋（正常系）。"""
    # 準備
    env = make_env({"docs/doc-1.yaml": "id: doc-1\n# TODO x\nname: 文書 1\n"})
    condition = Condition(field="body", op="regex", values=["^#\\s*TODO"])
    # 実行
    result = env.search(filter=condition, view="full", snippets=Snippets(before=0, after=0))
    # 検証
    assert result.items[0].snippets == [
        Snippet(lines=[SnippetLine(line=2, text="# TODO x", hit=True)])
    ]


def test_search_docs_when_id_values(make_env: Callable[..., SearchEnv]) -> None:
    """`order_by` なしで `id` の `eq` で絞ると、`values` の順に返す（正常系）。"""
    # 準備
    env = make_env(TWO_DOCS)
    condition = Condition(field="id", op="eq", values=["doc-2", "doc-1"])
    # 実行
    result = env.search(filter=condition)
    # 検証
    assert [item.id for item in result.items] == ["doc-2", "doc-1"]


def test_search_docs_when_id_values_and_order_by(make_env: Callable[..., SearchEnv]) -> None:
    """`order_by` を明示した `id` の `eq` は、`id` の昇順で返す（正常系）。"""
    # 準備
    env = make_env(TWO_DOCS)
    condition = Condition(field="id", op="eq", values=["doc-2", "doc-1"])
    # 実行
    result = env.search(filter=condition, order_by=[OrderKey(field="id")])
    # 検証
    assert [item.id for item in result.items] == ["doc-1", "doc-2"]


def test_search_docs_when_unreadable_file(make_env: Callable[..., SearchEnv]) -> None:
    """読めないファイル（正常系）。"""
    # 準備
    env = make_env({**TWO_DOCS, "docs/broken.yaml": "a: [1\n"})
    # 実行
    result = env.search()
    # 検証
    assert [item.id for item in result.items] == ["doc-1", "doc-2"]
    assert any("docs/broken.yaml" in note for note in result.notes)


def test_search_docs_when_read_validator(make_env: Callable[..., SearchEnv]) -> None:
    """読み取りの検査の警告（正常系）。"""
    # 準備
    code = "import json; print(json.dumps([{'path': 'x', 'rule': 'bad'}]))"
    validators = [ScriptEntry(id="v", run=[sys.executable, "-c", code], on=["read"])]
    env = make_env(TWO_DOCS, validators=validators, row_validators=["v"])
    # 実行
    result = env.search()
    # 検証
    assert result.total_count == 2
    assert any("bad" in note for note in result.notes)


def test_search_docs_when_unknown_field(make_env: Callable[..., SearchEnv]) -> None:
    """知らない項目（異常系）。"""
    # 準備
    env = make_env(TWO_DOCS)
    condition = Condition(field="nmae", op="eq", values=["x"])
    # 実行・検証
    with pytest.raises(InvalidArgumentError) as exc_info:
        env.search(filter=condition)
    assert exc_info.value.violations[0].path == "filter.field"
    assert "name" in exc_info.value.violations[0].fix


def test_search_docs_when_sources_all(
    tmp_path: Path,
    make_env: Callable[..., SearchEnv],
    write_files: Callable[[Path, dict[str, str]], None],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
) -> None:
    """全ての配信元（正常系）。"""
    # 準備
    table = DocumentTable(id="rules", type="yaml", paths=["docs/*.yaml"])
    config = make_source_config(documents=[table])
    sample_root = tmp_path / "sample"
    notes_root = tmp_path / "notes"
    other_root = tmp_path / "other"
    write_files(notes_root, {"docs/note-1.yaml": "id: note-1\nname: メモ\n"})
    write_files(other_root, {"docs/other-1.yaml": "id: other-1\nname: 他\n"})
    notes = make_served_source(
        id="notes", root=notes_root, config=config, scope_read=[str(sample_root)], scope_write=[]
    )
    other = make_served_source(
        id="other", root=other_root, config=config, scope_read=["/zzz"], scope_write=[]
    )
    env = make_env(TWO_DOCS, extra_sources=[notes, other])
    # 実行
    result = env.search(source="*")
    # 検証
    assert result.per_source == {"sample": 2, "notes": 1}
    assert {item.source for item in result.items} == {"sample", "notes"}


def test_search_docs_when_location(
    tmp_path: Path,
    git_repo: Callable[..., Path],
    make_source_config: Callable[..., SourceConfig],
    make_served_source: Callable[..., ServedSource],
    make_registry: Callable[..., SourceRegistry],
) -> None:
    """文書の場所と範囲（正常系）。"""
    # 準備
    root = git_repo(
        {
            "docs/doc-1.yaml": "id: doc-1\nname: 文書 1\ndescription: 1 件目\n",
            "data/list.yaml": "items:\n  - id: item-1\n    name: 項目 1\n",
        }
    )
    documents = [
        DocumentTable(id="rules", type="yaml", paths=["docs/*.yaml"]),
        DocumentTable(id="items", type="yaml", paths=["data/list.yaml"], records="items"),
    ]
    source = make_served_source(
        id="sample",
        root=root,
        config=make_source_config(documents=documents),
        is_git=True,
        repo_root=root,
    )
    store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
    env = SearchEnv(
        make_registry(source),
        store,
        DocumentChecker(store, timeout_sec=10),
        SeenStore(tmp_path / "seen.sqlite3", retention_days=7),
        root,
    )
    doc_1 = Condition(field="id", op="eq", values=["doc-1"])
    # 実行
    full = env.search(view="full")
    cut = env.search(filter=doc_1, view="full", max_chars_per_field=10)
    snippets = env.search(
        filter=Condition(field="body", op="contains", values=["文書"]),
        view="full",
        snippets=Snippets(context_lines=1, max_per_doc=3),
    )
    summary = env.search(filter=doc_1, view="summary")
    ids = env.search(filter=doc_1, view="ids")
    revision = env.search(filter=doc_1, view="full", ref="HEAD")
    # 検証
    assert [(item.id, item.path, item.scope) for item in full.items] == [
        ("doc-1", str(root / "docs" / "doc-1.yaml"), "full"),
        ("item-1", str(root / "data" / "list.yaml"), "section"),
    ]
    assert [(item.path, item.scope) for item in cut.items] == [
        (str(root / "docs" / "doc-1.yaml"), "section")
    ]
    assert [(item.path, item.scope) for item in snippets.items] == [
        (str(root / "docs" / "doc-1.yaml"), "section")
    ]
    assert [(item.path, item.scope) for item in summary.items] == [
        (str(root / "docs" / "doc-1.yaml"), "summary")
    ]
    assert [(item.path, item.scope) for item in ids.items] == [(None, None)]
    assert [(item.path, item.scope) for item in revision.items] == [(None, None)]
