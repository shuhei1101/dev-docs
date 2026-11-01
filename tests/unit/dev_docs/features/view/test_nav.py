from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.settings.types import SourceEntry
from dev_docs.features.sources.service import load_source
from dev_docs.features.sources.types import DocumentTable, ServedSource, SourceConfig
from dev_docs.features.view.nav import build_nav, mark_nav_changes
from dev_docs.features.view.types import NavItem, NavTab


def _tables() -> list[DocumentTable]:
    """文書の行を返す。"""
    return [
        DocumentTable(
            id="rules",
            paths=["docs/rule/*.yaml"],
            schema_path="schemas/rule.schema.yaml",
            title="規約",
        ),
        DocumentTable(
            id="architecture",
            paths=["docs/design/architecture.yaml"],
            schema_path="schemas/rule.schema.yaml",
        ),
        DocumentTable(
            id="prompts",
            paths=["prompts/files.yaml"],
            schema_path="schemas/rule.schema.yaml",
            records="files",
            body_file="path",
            title="プロンプト",
        ),
    ]


def test_build_nav(
    make_served_source: Callable[..., ServedSource],
    make_source_config: Callable[..., SourceConfig],
    make_document: Callable[..., Document],
) -> None:
    """group・page・auto（正常系）。"""
    # 準備
    nav = {
        "tabs": [
            {"title": "規約", "items": [{"auto": {"document": "rules", "group_by": "tags.lang"}}]},
            {
                "title": "設計書",
                "items": [{"group": "アーキテクチャ", "items": [{"page": "architecture"}]}],
            },
            {"title": "プロンプト", "items": [{"auto": {"document": "prompts"}}]},
        ]
    }
    source = make_served_source(config=make_source_config(documents=_tables(), nav=nav))
    documents = [
        make_document(
            id="rule-py",
            kind="rules",
            path="docs/rule/py.yaml",
            data={"tags": {"lang": "python"}},
            metadata={"tags": {"lang": "python"}},
        ),
        make_document(
            id="rule-ts",
            kind="rules",
            path="docs/rule/ts.yaml",
            data={"tags": {"lang": "typescript"}},
            metadata={"tags": {"lang": "typescript"}},
        ),
        make_document(id="architecture", kind="architecture", path="docs/design/architecture.yaml"),
        make_document(id="prompts/x", kind="prompts", path="prompts/x.md"),
    ]
    # 実行
    tabs = build_nav(source, documents)
    # 検証
    assert [tab.title for tab in tabs] == ["規約", "設計書", "プロンプト"]
    assert [(item.kind, item.title) for item in tabs[0].items] == [
        ("group", "python"),
        ("group", "typescript"),
    ]
    architecture = tabs[1].items[0]
    assert (architecture.kind, architecture.title) == ("group", "アーキテクチャ")
    assert (architecture.items[0].kind, architecture.items[0].path) == (
        "page",
        "docs/design/architecture",
    )
    assert [tab.active for tab in tabs] == [False, False, False]


def test_build_nav_when_no_nav(
    make_served_source: Callable[..., ServedSource],
    make_source_config: Callable[..., SourceConfig],
    make_document: Callable[..., Document],
) -> None:
    """nav が無い（正常系）。"""
    # 準備
    source = make_served_source(config=make_source_config(documents=_tables()[:2]))
    documents = [
        make_document(id="rule-py", kind="rules", path="docs/rule/py.yaml"),
        make_document(id="architecture", kind="architecture", path="docs/design/architecture.yaml"),
    ]
    # 実行
    tabs = build_nav(source, documents)
    # 検証
    assert [tab.title for tab in tabs] == ["規約", "architecture"]


def _page_item(title: str, path: str, **overrides: Any) -> NavItem:
    """page の項目を作る。"""
    return NavItem(kind="page", title=title, path=path, **overrides)


def _group_item(title: str, items: list[NavItem]) -> NavItem:
    """group の項目を作る。"""
    return NavItem(kind="group", title=title, items=items)


def test_mark_nav_changes() -> None:
    """追加・変更・変わっていない文書（正常系）。"""
    # 準備
    tabs = [
        NavTab(
            title="設計書",
            active=True,
            items=[_page_item("A", "docs/a"), _page_item("B", "docs/b"), _page_item("C", "docs/c")],
        )
    ]
    base_tabs = [
        NavTab(
            title="設計書",
            active=True,
            items=[_page_item("A", "docs/a"), _page_item("B", "docs/b")],
        )
    ]
    # 実行
    result = mark_nav_changes(
        tabs,
        base_tabs,
        versions={"docs/a": "v2", "docs/b": "v1", "docs/c": "v1"},
        base_versions={"docs/a": "v1", "docs/b": "v1"},
    )
    # 検証
    changes = {item.path: item.change for item in result[0].items}
    assert changes == {"docs/a": "modified", "docs/b": None, "docs/c": "added"}
    assert all(item.change is None for item in tabs[0].items)


def test_mark_nav_changes_when_deleted() -> None:
    """削除した文書を比較元の位置に差し込む（正常系）。"""
    # 準備
    tabs = [
        NavTab(
            title="設計書",
            active=True,
            items=[_group_item("設計", [_page_item("A", "docs/a"), _page_item("B", "docs/b")])],
        )
    ]
    base_tabs = [
        NavTab(
            title="設計書",
            active=True,
            items=[
                _group_item(
                    "設計",
                    [
                        _page_item("A", "docs/a"),
                        _page_item("X", "docs/x"),
                        _page_item("B", "docs/b"),
                    ],
                )
            ],
        )
    ]
    versions = {"docs/a": "v1", "docs/b": "v1"}
    # 実行
    result = mark_nav_changes(
        tabs, base_tabs, versions=versions, base_versions={**versions, "docs/x": "v1"}
    )
    # 検証
    items = result[0].items[0].items
    assert [(item.path, item.change) for item in items] == [
        ("docs/a", None),
        ("docs/x", "deleted"),
        ("docs/b", None),
    ]


def test_mark_nav_changes_when_group_missing() -> None:
    """比較元にだけある group の文書（正常系）。"""
    # 準備
    tabs = [NavTab(title="設計書", active=True, items=[_page_item("A", "docs/a")])]
    base_tabs = [
        NavTab(
            title="設計書",
            active=True,
            items=[_page_item("A", "docs/a"), _group_item("旧", [_page_item("Y", "docs/y")])],
        )
    ]
    # 実行
    result = mark_nav_changes(
        tabs,
        base_tabs,
        versions={"docs/a": "v1"},
        base_versions={"docs/a": "v1", "docs/y": "v1"},
    )
    # 検証
    last = result[0].items[-1]
    assert (last.path, last.change) == ("docs/y", "deleted")


MCP_FILTER = {"field": "tags", "op": "eq", "values": ["mcp"]}
NONE_FILTER = {"field": "tags", "op": "eq", "values": ["none"]}
TODAY = date(2026, 10, 31)


def _tagged_documents(make_document: Callable[..., Document]) -> list[Document]:
    """`tags: [mcp]` の文書を rules と notes に 1 件ずつ、タグの無い文書を rules に 1 件作る。"""
    return [
        make_document(
            id="rule-mcp",
            kind="rules",
            path="docs/rule/mcp.yaml",
            data={"tags": ["mcp"]},
            metadata={"tags": ["mcp"]},
        ),
        make_document(id="rule-plain", kind="rules", path="docs/rule/plain.yaml"),
        make_document(
            id="notes/mcp",
            kind="prompts",
            path="prompts/mcp.md",
            data={"tags": ["mcp"]},
            metadata={"tags": ["mcp"]},
        ),
    ]


def test_build_nav_when_filter(
    make_served_source: Callable[..., ServedSource],
    make_source_config: Callable[..., SourceConfig],
    make_document: Callable[..., Document],
) -> None:
    """条件で絞った auto（正常系）。"""
    # 準備
    nav = {
        "tabs": [
            {"title": "mcp", "items": [{"auto": {"filter": MCP_FILTER}}]},
            {
                "title": "規約の mcp",
                "items": [{"auto": {"document": "rules", "filter": MCP_FILTER}}],
            },
        ]
    }
    source = make_served_source(config=make_source_config(documents=_tables(), nav=nav))
    # 実行
    tabs = build_nav(source, _tagged_documents(make_document))
    # 検証
    assert [(item.kind, item.path) for item in tabs[0].items] == [
        ("page", "docs/rule/mcp"),
        ("page", "prompts/mcp"),
    ]
    assert [(item.kind, item.path) for item in tabs[1].items] == [("page", "docs/rule/mcp")]


def test_nav_auto_counts(make_document: Callable[..., Document]) -> None:
    """入れ子の auto を数える（正常系）。"""
    from dev_docs.features.search.fields import known_fields
    from dev_docs.features.view.nav import nav_auto_counts

    # 準備
    nav = {
        "tabs": [
            {"title": "mcp", "items": [{"auto": {"filter": MCP_FILTER}}]},
            {
                "title": "設計",
                "items": [{"group": "規約", "items": [{"auto": {"document": "rules"}}]}],
            },
            {"title": "none", "items": [{"auto": {"filter": NONE_FILTER}}]},
        ]
    }
    # 実行
    result = nav_auto_counts(
        nav, _tagged_documents(make_document), fields=known_fields([]), today=TODAY
    )
    # 検証
    assert [(count.path, count.tab, count.count) for count in result] == [
        ("nav.tabs[0].items[0].auto", "mcp", 2),
        ("nav.tabs[1].items[0].items[0].auto", "設計", 2),
        ("nav.tabs[2].items[0].auto", "none", 0),
    ]


def test_check_nav_filters() -> None:
    """知らない項目と無い行（異常系）。"""
    from dev_docs.features.search.fields import known_fields
    from dev_docs.features.view.nav import check_nav_filters

    # 準備
    nav = {
        "tabs": [
            {
                "title": "x",
                "items": [{"auto": {"filter": {"field": "nmae", "op": "eq", "values": ["x"]}}}],
            },
            {"title": "y", "items": [{"auto": {"document": "none"}}]},
        ]
    }
    # 実行
    result = check_nav_filters(nav, table_ids=["rules"], fields=known_fields([]))
    # 検証
    assert [item.path for item in result] == [
        "nav.tabs[0].items[0].auto.filter.field",
        "nav.tabs[1].items[0].auto.document",
    ]
    assert "name" in result[0].fix


def test_nav_warnings(
    make_alias_source_dir: Callable[..., Path],
    make_entry: Callable[..., SourceEntry],
    tmp_path: Path,
) -> None:
    """0 件の条件（正常系）。"""
    from dev_docs.features.view.nav import nav_warnings

    # 準備
    config = make_alias_source_dir(none_nav=True)
    source, _ = load_source(make_entry(str(config), source_id="sample"), index=0)
    assert source is not None
    store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
    # 実行
    result = nav_warnings(store, source, today=TODAY)
    # 検証
    assert [item.path for item in result] == ["nav.tabs[1].items[0].auto.filter"]
    assert result[0].rule.startswith("none:")


def test_nav_warnings_when_no_nav(
    make_alias_source_dir: Callable[..., Path],
    make_entry: Callable[..., SourceEntry],
    tmp_path: Path,
) -> None:
    """nav が無い（正常系）。"""
    from dev_docs.features.view.nav import nav_warnings

    # 準備
    config = make_alias_source_dir()
    source, _ = load_source(make_entry(str(config), source_id="sample"), index=0)
    assert source is not None
    store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
    # 実行
    result = nav_warnings(store, source, today=TODAY)
    # 検証
    assert result == []


OWNER_FILTER = {"field": "owner", "op": "eq", "values": ["alice"]}


def test_build_nav_when_records_filter(
    make_records_nav_source_dir: Callable[..., Path],
    make_entry: Callable[..., SourceEntry],
    tmp_path: Path,
) -> None:
    """records の行の 1 行の項目で絞った auto（正常系）。"""
    from dev_docs.features.access.types import Target

    # 準備
    config = make_records_nav_source_dir(
        "priority",
        "integer",
        {"a": 10, "b": 9},
        nav_filter={"field": "priority", "op": "gte", "values": ["10"]},
    )
    source, _ = load_source(make_entry(str(config), source_id="sample"), index=0)
    assert source is not None
    store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
    documents = store.load(Target(source, source.root, None, None, "read")).documents
    # 実行
    tabs = build_nav(source, documents)
    # 検証
    assert [(item.kind, item.path) for item in tabs[0].items] == [
        ("page", "notes/files/notes/a.md")
    ]


def test_nav_warnings_when_records_filter(
    make_records_nav_source_dir: Callable[..., Path],
    make_entry: Callable[..., SourceEntry],
    tmp_path: Path,
) -> None:
    """records の行の 1 行の項目の条件を警告しない（正常系）。"""
    from dev_docs.features.view.nav import nav_warnings

    # 準備
    config = make_records_nav_source_dir("owner", "string", {"a": "alice"}, nav_filter=OWNER_FILTER)
    source, _ = load_source(make_entry(str(config), source_id="sample"), index=0)
    assert source is not None
    store = DocumentStore(SnapshotStore(tmp_path / "snapshots"))
    # 実行
    result = nav_warnings(store, source, today=TODAY)
    # 検証
    assert result == []
