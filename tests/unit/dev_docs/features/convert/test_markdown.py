from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from dev_docs.features.convert.markdown import (
    item_heading,
    render_attributes,
    render_table,
    schema_to_markdown,
)
from dev_docs.features.convert.types import DiagramHead, DocumentLink, RenderContext
from dev_docs.integrations.project_index.types import IndexedDocument as Document

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
    """セクションの見出しの深さ（正常系）。"""
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
                                "kind": {"title": "種類"},
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
                    {"id": "a", "label": "A", "kind": "process"},
                    {"id": "b", "label": "B", "kind": "store"},
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
    assert "<!-- table: data closed +columns hide=ID -->\n| 表示 | ID | 種類 |" in result
    assert "<!-- table: data closed -->\n| 元 | 先 |" in result


def test_schema_to_markdown_when_er(make_document: Callable[..., Document]) -> None:
    """ER 図にテーブルの列を指定する（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "er": {"title": "ER 図", "x-shape": "diagram", "x-diagram": "er"},
            "tables": {"x-shape": "sections", "x-key": "name"},
        }
    }
    document = make_document(
        data={
            "name": "N",
            "er": {"entities": [{"name": "顧客"}]},
            "tables": [
                {
                    "name": "customers",
                    "title": "顧客",
                    "columns": [{"name": "id", "title": "顧客 ID", "type": "bigint"}],
                }
            ],
        }
    )
    # 実行
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    match = re.search(r"<!-- er -->\n\n```json\n(.*?)\n```\n\n<!-- /er -->", result, re.S)
    assert match is not None
    definition = json.loads(match.group(1))
    assert definition["tables"][0]["columns"][0]["name"] == "id"
    assert definition["tables"][0]["columns"][0]["type"] == "bigint"


SCENARIO_SCHEMA: dict[str, Any] = {
    "properties": {
        "name": {"type": "string"},
        "flow": {"x-heading": "処理の流れ"},
        "scenarios": {"x-shape": "sections", "x-key": "name"},
    }
}
SCENARIO_DATA: dict[str, Any] = {
    "name": "N",
    "flow": "a",
    "scenarios": [{"name": "正常シナリオ"}],
}


def test_item_heading() -> None:
    """x-heading を持つ項目（正常系）。"""
    # 実行
    result = item_heading(SCENARIO_DATA, SCENARIO_SCHEMA, "flow")
    # 検証
    assert result == "処理の流れ"


def test_item_heading_when_section() -> None:
    """sections の要素（正常系）。"""
    # 実行
    result = item_heading(SCENARIO_DATA, SCENARIO_SCHEMA, "scenarios[正常シナリオ]")
    # 検証
    assert result == "正常シナリオ"


def test_item_heading_when_not_heading() -> None:
    """見出しにならない項目と無い項目（正常系）。"""
    # 実行
    plain = item_heading(SCENARIO_DATA, SCENARIO_SCHEMA, "name")
    missing = item_heading(SCENARIO_DATA, SCENARIO_SCHEMA, "scenarios[無い]")
    # 検証
    assert plain is None
    assert missing is None


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


def test_schema_to_markdown_when_foreign_key(make_document: Callable[..., Document]) -> None:
    """同じ文書のテーブルへの外部キー（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "tables": {
                "x-shape": "sections",
                "x-key": "name",
                "items": {
                    "properties": {
                        "columns": {"x-heading": "カラム", "x-shape": "table", "items": {}},
                    }
                },
            }
        }
    }
    document = make_document(
        data={
            "name": "N",
            "tables": [
                {"name": "tasks", "title": "タスク", "columns": [{"name": "id"}]},
                {
                    "name": "comments",
                    "title": "コメント",
                    "columns": [{"name": "task_id", "foreign_key": {"table": "タスク.ID"}}],
                },
            ],
        }
    )
    # 実行
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    assert "[タスク.ID](#tasks)" in result


def test_schema_to_markdown_when_foreign_key_physical_name(
    make_document: Callable[..., Document],
) -> None:
    """物理名で記載した同じ文書のテーブルへの外部キー（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "tables": {
                "x-shape": "sections",
                "x-key": "name",
                "items": {
                    "properties": {
                        "columns": {"x-heading": "カラム", "x-shape": "table", "items": {}},
                    }
                },
            }
        }
    }
    document = make_document(
        data={
            "name": "N",
            "tables": [
                {"name": "tasks", "title": "タスク", "columns": [{"name": "id"}]},
                {
                    "name": "comments",
                    "title": "コメント",
                    "columns": [{"name": "task_id", "foreign_key": {"table": "tasks.id"}}],
                },
            ],
        }
    )
    # 実行
    result = schema_to_markdown(document, schema, CONTEXT)
    # 検証
    assert "[tasks.id](#tasks)" in result


def test_render_table() -> None:
    """セルの記載方法（正常系）。"""
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
    context = RenderContext(
        links={
            "dev/er/ユーザー.yaml": DocumentLink(
                title="ER 図: ユーザー", path="dev/er/ユーザー.yaml"
            )
        },
        issue_url=None,
        path="dev/er/タスク.yaml",
        anchors={"タスク": "tasks"},
    )
    rows: list[dict[str, Any]] = [
        {"name": "task_id", "foreign_key": {"table": "タスク.ID"}},
        {
            "name": "user_id",
            "foreign_key": {"table": "ユーザー/ユーザー.ID", "on_delete": "CASCADE"},
        },
        {"name": "other_id", "foreign_key": {"table": "不明.ID"}},
        {"name": "meta", "foreign_key": {"a": 1, "b": 2}},
    ]
    # 実行
    result = render_table(rows, {}, table_key="er:columns", context=context)
    # 検証
    assert "[タスク.ID](#tasks)" in result
    assert f"[ユーザー/ユーザー.ID]({quote('ユーザー.yaml')})" in result
    assert "| other_id | 不明.ID |" in result
    assert "a: 1、b: 2" in result
    assert "件" not in result


def test_render_table_when_physical_name() -> None:
    """物理名で記載した同じ文書のテーブルへの外部キー（正常系）。"""
    # 準備
    context = RenderContext(
        links={},
        issue_url=None,
        path="dev/er/タスク.yaml",
        anchors={"タスク": "tasks"},
        table_titles={"tasks": "タスク", "タスク": "タスク"},
    )
    rows: list[dict[str, Any]] = [{"name": "task_id", "foreign_key": {"table": "tasks.id"}}]
    # 実行
    result = render_table(rows, {}, table_key="er:columns", context=context)
    # 検証
    assert "[tasks.id](#tasks)" in result


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


def test_schema_to_markdown_when_decisions(make_document: Callable[..., Document]) -> None:
    """箇条書きの検討事項のリンク（正常系）。"""
    # 準備
    schema = {
        "properties": {
            "name": {"type": "string"},
            "decisions": {"type": "array", "title": "検討事項"},
            "tags": {"type": "array", "title": "タグ"},
        }
    }
    document = make_document(data={"name": "N", "decisions": ["D-1", "D-2"], "tags": ["D-1"]})
    context = RenderContext(
        links={}, issue_url=None, path="rules/doc-1.yaml", decisions=frozenset({"D-1"})
    )
    # 実行
    result = schema_to_markdown(document, schema, context)
    # 検証
    assert "[D-1](../_decisions/D-1)" in result
    assert result.count("[D-1]") == 1
    assert "D-2" in result
    assert "[D-2]" not in result


def test_render_table_when_wide() -> None:
    """説明の列（正常系）。"""
    # 準備
    schema = {"properties": {"name": {"title": "名前"}, "description": {"title": "説明"}}}
    rows = [{"name": "a", "description": "長い説明"}]
    # 実行
    result = render_table(rows, schema, table_key="d:items", context=CONTEXT)
    # 検証
    assert "<!-- table: data wide=説明 -->" in result


def test_render_table_when_decisions() -> None:
    """表のセルの検討事項のリンク（正常系）。"""
    # 準備
    schema = {"properties": {"name": {"title": "名前"}, "decisions": {"title": "検討事項"}}}
    rows = [{"name": "a", "decisions": ["D-1", "D-2"]}]
    context = RenderContext(
        links={}, issue_url=None, path="rules/doc-1.yaml", decisions=frozenset({"D-1"})
    )
    # 実行
    result = render_table(rows, schema, table_key="d:items", context=context)
    # 検証
    assert "| a | [D-1](../_decisions/D-1)・D-2 |" in result


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
