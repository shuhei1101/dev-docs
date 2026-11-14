from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dev_docs.features.convert.service import ConvertService
from dev_docs.features.convert.types import ConvertFailure
from dev_docs.integrations.project_index.types import (
    DocumentDetail,
    DocumentRow,
    IndexedDocument,
    IndexFailure,
    SourceView,
)

ITEMS_SCHEMA = {
    "properties": {
        "name": {"type": "string"},
        "items": {
            "type": "array",
            "x-heading": "一覧",
            "x-shape": "table",
            "items": {"type": "object", "properties": {"id": {"title": "ID"}}},
        },
    }
}

# 本文の `body` と、`x-heading: 処理の流れ` の `flow` を持つスキーマ
LINK_SCHEMA = {
    "properties": {
        "name": {"type": "string"},
        "body": {"type": "string", "title": "本文"},
        "flow": {"type": "string", "x-heading": "処理の流れ"},
    }
}

# records の行の 1 要素のスキーマ
RECORD_SCHEMA = {
    "properties": {
        "path": {"type": "string", "title": "ファイルのパス"},
        "summary": {"type": "string"},
    }
}


def _view(make_view: Callable[..., SourceView], schema: dict[str, Any], **row: Any) -> SourceView:
    """行 rules を 1 つ持つ配信元の表示の設定を作る。"""
    values: dict[str, Any] = {"id": "rules", "paths": ["rules/*.yaml"], "schema": schema, **row}
    return make_view(documents=[DocumentRow(**values)])


def test_convert_service_render(
    make_view: Callable[..., SourceView], make_document: Callable[..., IndexedDocument]
) -> None:
    """スキーマ駆動（正常系）。"""
    # 準備
    document = make_document(data={"name": "N", "items": [{"id": "a"}]})
    detail = DocumentDetail(document=document)
    # 実行
    result = ConvertService().render(
        _view(make_view, ITEMS_SCHEMA), detail, [document], linkable=[]
    )
    # 検証
    assert isinstance(result, str)
    assert result.startswith("# N")


def test_convert_service_render_when_converter(
    make_view: Callable[..., SourceView], make_document: Callable[..., IndexedDocument]
) -> None:
    """project-index の変換の結果を使用する（正常系）。"""
    # 準備
    document = make_document(data={"name": "N"})
    detail = DocumentDetail(document=document, markdown="# 変換した\n")
    # 実行
    result = ConvertService().render(
        _view(make_view, ITEMS_SCHEMA, converter="c"), detail, [document], linkable=[]
    )
    # 検証
    assert result == "# 変換した\n"


def test_convert_service_render_when_failure(
    make_view: Callable[..., SourceView], make_document: Callable[..., IndexedDocument]
) -> None:
    """project-index の変換の失敗（正常系）。"""
    # 準備
    failure = IndexFailure(reason="timeout", kind="rules", detail="45 秒", script="python conv.py")
    detail = DocumentDetail(document=make_document(), failure=failure)
    # 実行
    result = ConvertService().render(_view(make_view, {}), detail, [], linkable=[])
    # 検証
    assert isinstance(result, ConvertFailure)
    assert (result.reason, result.script) == ("timeout", "python conv.py")


def test_convert_service_render_when_markdown(
    make_view: Callable[..., SourceView], make_document: Callable[..., IndexedDocument]
) -> None:
    """Markdown の本文（正常系）。"""
    # 準備
    view = _view(make_view, ITEMS_SCHEMA, records="files")
    markdown = make_document(body="# 本文\n\n段落\n", body_path="docs/a.md")
    code = make_document(
        data={"name": "部品", "path": "a.py"}, body="a = 1\n", body_path="src/a.py"
    )
    service = ConvertService()
    # 実行
    markdown_result = service.render(view, DocumentDetail(document=markdown), [], linkable=[])
    code_result = service.render(view, DocumentDetail(document=code), [], linkable=[])
    # 検証
    assert markdown_result == "# 本文\n\n段落\n"
    assert isinstance(code_result, str)
    assert code_result.startswith("# 部品")


def test_convert_service_render_when_records(
    make_view: Callable[..., SourceView], make_document: Callable[..., IndexedDocument]
) -> None:
    """records の行の要素を 1 行のスキーマで変換する（正常系）。"""
    # 準備
    view = make_view(
        documents=[
            DocumentRow(
                id="notes", paths=["notes/files.yaml"], schema=RECORD_SCHEMA, records="files"
            )
        ]
    )
    document = make_document(
        id="notes/a",
        kind="notes",
        path="notes/files.yaml",
        record_index=0,
        data={"path": "a.md", "summary": "説明"},
        body="",
        metadata={"id": "notes/a", "name": "a"},
    )
    # 実行
    result = ConvertService().render(view, DocumentDetail(document=document), [], linkable=[])
    # 検証
    assert isinstance(result, str)
    assert "a.md" in result
    assert "説明" in result


def test_convert_service_render_when_id_link(
    make_view: Callable[..., SourceView], make_document: Callable[..., IndexedDocument]
) -> None:
    """本文の id のリンクを他の文書の見出しへ解決する（正常系）。"""
    # 準備
    document_a = make_document(
        id="a",
        path="rules/a.yaml",
        data={"name": "A", "body": "[B](id:b#flow) を読む"},
        metadata={"id": "a", "name": "A"},
    )
    document_b = make_document(
        id="b",
        path="rules/b.yaml",
        data={"name": "B", "flow": "流れ"},
        metadata={"id": "b", "name": "B"},
    )
    # 実行
    result = ConvertService().render(
        _view(make_view, LINK_SCHEMA),
        DocumentDetail(document=document_a),
        [document_a, document_b],
        linkable=[],
    )
    # 検証
    assert isinstance(result, str)
    assert "[B](b.yaml#処理の流れ) を読む" in result


def test_convert_service_finish() -> None:
    """表のキーを取り出す（正常系）。"""
    # 準備
    markdown = (
        "<!-- dev-docs-table: sample:items -->\n| a |\n| --- |\n| 1 |\n\n"
        "段落\n\n| b |\n| --- |\n| 2 |\n"
    )
    # 実行
    result = ConvertService().finish(markdown, "sample", {})
    # 検証
    assert "dev-docs-table" not in result.markdown
    assert result.table_keys == ["sample:items", "sample:table[1]"]


def test_convert_service_finish_when_embed() -> None:
    """埋め込んだ表のキー（正常系）。"""
    # 準備
    markdown = "<!-- embed: data/list.yaml#items -->\n"
    embedded = {"data/list.yaml": {"items": [{"id": "a"}, {"id": "b"}]}}
    # 実行
    result = ConvertService().finish(markdown, "sample", embedded)
    # 検証
    assert "| a |" in result.markdown
    assert "| b |" in result.markdown
    assert "embed:data/list.yaml#items" in result.table_keys
