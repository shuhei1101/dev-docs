from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dev_docs.features.convert.markdown import render_table, schema_to_markdown
from dev_docs.features.documents.types import Document

ITEMS_SCHEMA: dict[str, Any] = {
    "properties": {
        "name": {"type": "string"},
        "items": {
            "type": "array",
            "title": "一覧",
            "x-heading": "一覧",
            "x-shape": "table",
            "items": {
                "type": "object",
                "properties": {"id": {"title": "ID"}, "name": {"title": "名前"}},
            },
        },
    }
}


def test_schema_to_markdown(make_document: Callable[..., Document]) -> None:
    """見出しと表（正常系）。"""
    # 準備
    document = make_document(
        data={"name": "N", "items": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]}
    )
    # 実行
    result = schema_to_markdown(document, ITEMS_SCHEMA)
    # 検証
    assert result.index("# N") < result.index("## 一覧") < result.index("| ID | 名前 |")


def test_schema_to_markdown_when_sections(make_document: Callable[..., Document]) -> None:
    """節の見出しの深さ（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "name": {"type": "string"},
            "groups": {
                "type": "array",
                "x-heading": "グループ",
                "x-shape": "sections",
                "x-key": "name",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "detail": {"type": "string", "x-heading": "詳細"},
                    },
                },
            },
        }
    }
    document = make_document(data={"name": "N", "groups": [{"name": "G1", "detail": "text"}]})
    # 実行
    result = schema_to_markdown(document, schema)
    # 検証
    assert "\n### G1\n" in result
    assert "\n#### 詳細\n" in result


def test_schema_to_markdown_when_no_schema(make_document: Callable[..., Document]) -> None:
    """スキーマが無い（正常系）。"""
    # 準備
    document = make_document(data={"name": "N", "text": "t", "tags": ["a", "b"], "obj": {"k": "v"}})
    # 実行
    result = schema_to_markdown(document, {})
    # 検証
    assert "text" in result
    assert "- a" in result
    assert "- b" in result
    assert "k" in result
    assert "v" in result


def test_render_table() -> None:
    """セルの書き方（正常系）。"""
    # 準備
    rows = [
        {"a": "x|y\nz", "b": ["a", "b"], "c": [{"k": 1}, {"k": 2}]},
        {"a": "p", "b": ["c"], "c": [{"k": 3}]},
    ]
    # 実行
    result = render_table(rows, {}, table_key="rules:items")
    # 検証
    assert result.startswith("<!-- dev-docs-table: rules:items -->")
    assert "x\\|y<br>z" in result
    assert "a・b" in result
    assert "2 件" in result
