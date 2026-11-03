from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from dev_docs.features.convert.markdown import (
    render_attributes,
    render_table,
    schema_to_markdown,
)
from dev_docs.features.convert.types import DiagramHead, DocumentLink, RenderContext
from dev_docs.features.documents.types import Document

CONTEXT = RenderContext(links={}, issue_url=None, path="rules/doc-1.yaml")
HEAD = DiagramHead(title="図", scope="文書", updated="-")

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
    result = schema_to_markdown(document, ITEMS_SCHEMA, CONTEXT)
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
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    assert "\n### G1\n" in result
    assert "\n#### 詳細\n" in result


def test_schema_to_markdown_when_no_schema(make_document: Callable[..., Document]) -> None:
    """スキーマが無い（正常系）。"""
    # 準備
    document = make_document(data={"name": "N", "text": "t", "tags": ["a", "b"], "obj": {"k": "v"}})
    # 実行
    result = schema_to_markdown(document, {}, CONTEXT)
    # 検証
    assert "**text**: t" in result
    assert "- a" in result
    assert "- b" in result
    assert "**k**: v" in result


def test_schema_to_markdown_when_title_and_lead(make_document: Callable[..., Document]) -> None:
    """見出しとリードのキー（正常系）。"""
    # 準備
    document = make_document(data={"title": "A", "lead": "B"})
    # 実行
    result = schema_to_markdown(document, {}, CONTEXT)
    # 検証
    assert result.startswith("# A\n\nB\n")
    assert "**title**" not in result
    assert "**lead**" not in result


def test_schema_to_markdown_when_hidden(make_document: Callable[..., Document]) -> None:
    """内部向けのキー（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "docs_index": {"type": "boolean", "title": "索引", "x-hidden": True},
            "items": {
                "type": "array",
                "x-shape": "table",
                "items": {
                    "properties": {
                        "name": {"title": "名前"},
                        "secret": {"title": "内部", "x-hidden": True},
                    }
                },
            },
        }
    }
    document = make_document(
        data={"name": "N", "docs_index": True, "items": [{"name": "a", "secret": "zzz"}]}
    )
    # 実行
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    assert "索引" not in result
    assert "内部" not in result
    assert "zzz" not in result


def test_schema_to_markdown_when_attributes(make_document: Callable[..., Document]) -> None:
    """スカラーの並び（正常系）。"""
    # 準備
    three = make_document(data={"name": "N", "a": "1", "b": "2", "c": "3"})
    two = make_document(data={"name": "N", "a": "1", "b": "2"})
    # 実行
    three_result = schema_to_markdown(three, {}, CONTEXT)
    two_result = schema_to_markdown(two, {}, CONTEXT)
    # 検証
    assert "| 項目 | 値 |" in three_result
    assert "| a | 1 |" in three_result
    assert "**a**" not in three_result
    assert "| 項目 | 値 |" not in two_result
    assert "**a**: 1" in two_result


def test_schema_to_markdown_when_multiline(make_document: Callable[..., Document]) -> None:
    """複数行の値（正常系）。"""
    # 準備
    schema = {"properties": {"run": {"type": "string", "title": "全件実行"}}}
    document = make_document(data={"name": "N", "run": "```bash\nuv run pytest\n```"})
    # 実行
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    assert "**全件実行**\n\n```bash\nuv run pytest\n```" in result
    assert "**全件実行**: ```" not in result


def test_schema_to_markdown_when_diagram(make_document: Callable[..., Document]) -> None:
    """図と元データの表（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "flow": {
                "title": "流れ",
                "x-shape": "diagram",
                "x-diagram": "flowchart",
                "properties": {
                    "nodes": {
                        "items": {
                            "properties": {
                                "id": {"title": "ID"},
                                "label": {"title": "表示"},
                                "shape": {"title": "形"},
                            }
                        }
                    },
                    "edges": {
                        "items": {"properties": {"from": {"title": "元"}, "to": {"title": "先"}}}
                    },
                },
            }
        }
    }
    document = make_document(
        data={
            "name": "N",
            "flow": {
                "nodes": [
                    {"id": "a", "label": "A", "shape": "rect"},
                    {"id": "b", "label": "B", "shape": "round"},
                ],
                "edges": [{"from": "a", "to": "b"}],
            },
        },
        updated=datetime(2026, 11, 3, 9, 0, 0, tzinfo=UTC),
    )
    # 実行
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    assert "<!-- flow -->" in result
    assert '"updated": "2026-11-03"' in result
    assert "<!-- table: data closed +columns hide=ID,形 -->\n| 表示 | ID | 形 |" in result
    assert "<!-- table: data closed -->\n| 元 | 先 |" in result


def test_schema_to_markdown_when_test_files(make_document: Callable[..., Document]) -> None:
    """対応テストファイル（正常系）。"""
    # 準備
    context = RenderContext(
        links={"tests/test_a.py": DocumentLink(title="test_a", path="tests/test_a.py")},
        issue_url=None,
        path="rules/doc-1.yaml",
    )
    schema = {"properties": {"test_file": {"type": "string", "title": "対応テストファイル"}}}
    document = make_document(data={"name": "N", "test_file": "tests/test_a.py"})
    # 実行
    result = schema_to_markdown(document, schema, context)
    # 検証
    assert "<!-- table: plain closed -->" in result
    assert "| 対応テストファイル |" in result
    assert "[test_a](../tests/test_a.py)" in result


def test_schema_to_markdown_when_examples(make_document: Callable[..., Document]) -> None:
    """リクエスト例とレスポンス例（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "request_example": {"type": "string", "title": "リクエスト例"},
            "response_example": {"type": "string", "title": "レスポンス例"},
        }
    }
    document = make_document(
        data={"name": "N", "request_example": "GET /a", "response_example": "200"}
    )
    # 実行
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    start, end = result.index("<!-- tabs -->"), result.index("<!-- /tabs -->")
    assert result.count("## リクエスト例", start, end) == 1
    assert result.count("## レスポンス例", start, end) == 1


def test_render_table() -> None:
    """セルの書き方（正常系）。"""
    # 準備
    rows = [
        {"a": "x|y\nz", "b": ["a", "b"], "c": True},
        {"a": "p", "b": ["c"], "c": False},
    ]
    # 実行
    result = render_table(rows, {}, table_key="rules:items", context=CONTEXT)
    # 検証
    assert result.startswith("<!-- dev-docs-table: rules:items -->")
    assert "x\\|y<br>z" in result
    assert "a・b" in result
    assert "| p | c |  |" in result
    assert "| ✓ |" in result


def test_render_table_when_objects() -> None:
    """オブジェクトのリストのセル（正常系）。"""
    # 準備
    rows: list[dict[str, Any]] = [
        {"name": "user_id", "references": [{"table": "users", "column": "id"}]},
        {"name": "meta", "references": {"a": 1, "b": 2}},
    ]
    # 実行
    result = render_table(rows, {}, table_key="er:columns", context=CONTEXT)
    # 検証
    assert "[users.id](#users)" in result
    assert "a: 1、b: 2" in result
    assert "件" not in result


def test_render_table_when_closed_and_hidden() -> None:
    """閉じた表と隠す列（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "id": {"title": "ID"},
            "label": {"title": "表示"},
            "shape": {"title": "形"},
            "kind": {"title": "種類"},
        }
    }
    rows = [{"id": "a", "label": "A", "shape": "rect", "kind": "process"}]
    # 実行
    result = render_table(
        rows,
        schema,
        table_key="d:nodes",
        context=CONTEXT,
        closed=True,
        first="label",
        hidden=["id", "shape"],
    )
    # 検証
    assert "<!-- table: data closed +columns hide=ID,形 -->" in result
    assert "| 表示 | ID | 形 | 種類 |" in result


def test_render_table_when_wide() -> None:
    """説明の列（正常系）。"""
    # 準備
    schema = {"properties": {"name": {"title": "名前"}, "description": {"title": "説明"}}}
    rows = [{"name": "a", "description": "長い説明"}]
    # 実行
    result = render_table(rows, schema, table_key="d:items", context=CONTEXT)
    # 検証
    assert "<!-- table: data wide=説明 -->" in result


def test_render_attributes() -> None:
    """項目と値（正常系）。"""
    # 実行
    result = render_attributes([("種類", "A"), ("必須", True), ("上限", 3)], CONTEXT, HEAD)
    # 検証
    assert "| 項目 | 値 |" in result
    assert "| 種類 | A |" in result
    assert "| 必須 | ✓ |" in result
    assert "| 上限 | 3 |" in result


def test_render_attributes_when_long() -> None:
    """長い値（正常系）。"""
    # 準備
    long_value = "あ" * 120
    # 実行
    result = render_attributes([("長い", long_value), ("複数行", "1 行目\n2 行目")], CONTEXT, HEAD)
    # 検証
    assert f"| 長い | {'あ' * 100}… |" in result
    assert "| 複数行 | 1 行目… |" in result
    assert f"<!-- row-detail: 1 -->\n\n{long_value}\n\n<!-- /row-detail -->" in result
    assert "<!-- row-detail: 2 -->\n\n1 行目\n2 行目\n\n<!-- /row-detail -->" in result
