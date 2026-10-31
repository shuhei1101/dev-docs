from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dev_docs.features.documents.types import Document
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
