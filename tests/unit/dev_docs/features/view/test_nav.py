from __future__ import annotations

from collections.abc import Callable

from dev_docs.features.documents.types import Document
from dev_docs.features.sources.types import DocumentTable, ServedSource, SourceConfig
from dev_docs.features.view.nav import build_nav


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
