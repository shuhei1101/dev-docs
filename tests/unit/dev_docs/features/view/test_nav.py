from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from dev_docs.features.view import nav as nav_module
from dev_docs.features.view.nav import build_nav, mark_nav_changes
from dev_docs.features.view.types import NavItem, NavTab
from dev_docs.integrations.project_index.types import DocumentRow, SourceView
from dev_docs.integrations.project_index.types import IndexedDocument as Document


def _tables() -> list[DocumentRow]:
    """文書の行を返す。"""
    return [
        DocumentRow(
            id="rules",
            paths=["docs/rule/*.yaml"],
            schema={},
            title="規約",
        ),
        DocumentRow(
            id="architecture",
            paths=["docs/design/architecture.yaml"],
            schema={},
        ),
        DocumentRow(
            id="prompts",
            paths=["prompts/files.yaml"],
            schema={},
            records="files",
            title="プロンプト",
        ),
    ]


def test_build_nav(
    make_view: Callable[..., SourceView],
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
    view = make_view(documents=_tables(), nav=nav)
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
    tabs = build_nav(view, documents)
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
    make_view: Callable[..., SourceView],
    make_document: Callable[..., Document],
) -> None:
    """nav が無いときは行ごとのタブをフォルダで束ねる（正常系）。"""
    # 準備
    tables = [
        DocumentRow(id="docs", paths=["docs/**/*.yaml"], schema={}),
        DocumentRow(id="notes", paths=["notes/*.md"], schema={}),
    ]
    view = make_view(documents=tables)
    documents = [
        make_document(id="a", kind="docs", path="docs/a.yaml"),
        make_document(id="b", kind="docs", path="docs/sub/b.yaml"),
        make_document(id="c", kind="notes", path="notes/c.md"),
    ]
    # 実行
    tabs = build_nav(view, documents)
    # 検証
    assert [tab.title for tab in tabs] == ["docs", "notes"]
    assert [_shape(item) for item in tabs[0].items] == ["docs/a", ("sub", ["docs/sub/b"])]
    assert [_shape(item) for item in tabs[1].items] == ["notes/c"]


def test_build_nav_when_group_by_folder(
    make_view: Callable[..., SourceView],
    make_document: Callable[..., Document],
) -> None:
    """フォルダで束ねる auto と手で書いた page の重なり（正常系）。"""
    # 準備
    nav = {
        "tabs": [
            {
                "title": "ルール",
                "items": [
                    {"group": "共通", "items": [{"page": "rules/common"}]},
                    {"auto": {"document": "rules", "group_by": "@folder"}},
                ],
            }
        ]
    }
    view = make_view(documents=_folder_tables(), nav=nav)
    documents = _rule_documents(
        make_document,
        [
            "rules/common.yaml",
            "rules/lang/index.yaml",
            "rules/lang/ts.yaml",
            "rules/lang/py/style.yaml",
        ],
    )
    # 実行
    tabs = build_nav(view, documents)
    # 検証
    assert [_shape(item) for item in tabs[0].items] == [
        ("共通", ["rules/common"]),
        ("lang", ["rules/lang/index", "rules/lang/ts", ("py", ["rules/lang/py/style"])]),
    ]


def _shape(item: NavItem) -> Any:
    """項目を、page はパス、group は（名前・子の並び）にして返す。"""
    if item.kind == "page":
        return item.path
    return (item.title, [_shape(child) for child in item.items])


def _folder_tables() -> list[DocumentRow]:
    """`paths: [rules/**/*.yaml]` の行 `rules` を返す。"""
    return [DocumentRow(id="rules", paths=["rules/**/*.yaml"], schema={})]


def _rule_documents(make_document: Callable[..., Document], paths: list[str]) -> list[Document]:
    """行 `rules` の文書を、ファイル名を ID にして作る。"""
    return [
        make_document(
            id=Path(path).stem if Path(path).stem != "index" else "lang-index",
            kind="rules",
            path=path,
        )
        for path in paths
    ]


def test_folder_items(make_document: Callable[..., Document]) -> None:
    """入れ子のフォルダと並び（正常系）。"""
    # 準備
    rows = {row.id: row for row in _folder_tables()}
    documents = _rule_documents(
        make_document,
        [
            "rules/z.yaml",
            "rules/a.yaml",
            "rules/lang/ts.yaml",
            "rules/lang/index.yaml",
            "rules/lang/py/style.yaml",
            "rules/b/x.yaml",
        ],
    )
    # 実行
    items = nav_module._folder_items(documents, rows=rows)
    # 検証
    assert [_shape(item) for item in items] == [
        "rules/a",
        "rules/z",
        ("b", ["rules/b/x"]),
        ("lang", ["rules/lang/index", "rules/lang/ts", ("py", ["rules/lang/py/style"])]),
    ]


def test_folder_items_when_multiple_globs(make_document: Callable[..., Document]) -> None:
    """先に並ぶ glob の起点を使う（正常系）。"""
    # 準備
    row = DocumentRow(
        id="docs",
        paths=["docs/guide/**/*.md", "docs/**/*.md"],
        schema={},
    )
    documents = [make_document(id="a", kind="docs", path="docs/guide/start/a.md")]
    # 実行
    items = nav_module._folder_items(documents, rows={"docs": row})
    # 検証
    assert [_shape(item) for item in items] == [("start", ["docs/guide/start/a"])]


def test_folder_items_when_records(make_document: Callable[..., Document]) -> None:
    """管理用の YAML の行の文書は束ねない（正常系）。"""
    # 準備
    row = DocumentRow(
        id="notes",
        paths=["notes/index/files.yaml"],
        schema={},
        records="files",
    )
    documents = [
        make_document(id="b.md", kind="notes", path="notes/index/files.yaml", record_index=1),
        make_document(id="a.md", kind="notes", path="notes/index/files.yaml", record_index=0),
    ]
    # 実行
    items = nav_module._folder_items(documents, rows={"notes": row})
    # 検証
    assert all(item.kind == "page" for item in items)
    assert [item.path for item in items] == [
        "notes/index/files/a.md",
        "notes/index/files/b.md",
    ]


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
    make_view: Callable[..., SourceView],
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
    view = make_view(documents=_tables(), nav=nav)
    # 実行
    tabs = build_nav(view, _tagged_documents(make_document))
    # 検証
    assert [(item.kind, item.path) for item in tabs[0].items] == [
        ("page", "docs/rule/mcp"),
        ("page", "prompts/mcp"),
    ]
    assert [(item.kind, item.path) for item in tabs[1].items] == [("page", "docs/rule/mcp")]


OWNER_FILTER = {"field": "owner", "op": "eq", "values": ["alice"]}


# records の行の 1 要素のスキーマ
PRIORITY_SCHEMA = {
    "properties": {"path": {"type": "string"}, "priority": {"type": "integer"}},
}


def test_build_nav_when_records_filter(
    make_view: Callable[..., SourceView], make_document: Callable[..., Document]
) -> None:
    """records の行の 1 行の項目で絞った auto（正常系）。"""
    # 準備
    nav = {
        "tabs": [
            {
                "title": "メモ",
                "items": [
                    {
                        "auto": {
                            "document": "notes",
                            "filter": {"field": "priority", "op": "gte", "values": ["10"]},
                        }
                    }
                ],
            }
        ]
    }
    row = DocumentRow(
        id="notes", paths=["notes/files.yaml"], schema=PRIORITY_SCHEMA, records="files"
    )
    view = make_view(documents=[row], nav=nav)
    documents = [
        make_document(
            id=f"notes/{name}.md",
            kind="notes",
            path="notes/files.yaml",
            record_index=index,
            data={"path": f"{name}.md", "priority": priority},
            metadata={"id": f"notes/{name}.md"},
        )
        for index, (name, priority) in enumerate([("a", 10), ("b", 9)])
    ]
    # 実行
    tabs = build_nav(view, documents)
    # 検証
    assert [(item.kind, item.path) for item in tabs[0].items] == [
        ("page", "notes/files/notes/a.md")
    ]
