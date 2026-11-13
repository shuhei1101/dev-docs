from __future__ import annotations

from collections.abc import Callable

import pytest

from dev_docs.features.documents.fields import get_field, parse_field_path, with_row_metadata
from dev_docs.integrations.project_index.types import DocumentRow, SourceView
from dev_docs.integrations.project_index.types import IndexedDocument as Document
from dev_docs.shared.errors import InvalidArgumentError


def test_parse_field_path() -> None:
    """キーと位置（正常系）。"""
    # 実行
    result = parse_field_path("a.b[0][1].c")
    # 検証
    assert result == ["a", "b", 0, 1, "c"]


@pytest.mark.parametrize(
    "path", [pytest.param("a..b", id="empty-key"), pytest.param("a[x-y]", id="bad-index")]
)
def test_parse_field_path_when_invalid(path: str) -> None:
    """空のキーと数字でない位置（異常系）。"""
    # 実行・検証
    with pytest.raises(InvalidArgumentError) as exc_info:
        parse_field_path(path)
    assert exc_info.value.violations[0].path == path


def test_parse_field_path_when_selector() -> None:
    """全ての要素と真偽値のキーで選ぶ要素（正常系）。"""
    from dev_docs.features.documents.fields import ArraySelector

    # 実行
    results = [parse_field_path("tags[].name"), parse_field_path("tags[main].name")]
    # 検証
    assert results == [
        ["tags", ArraySelector(key=None), "name"],
        ["tags", ArraySelector(key="main"), "name"],
    ]


def test_get_field() -> None:
    """入れ子と位置（正常系）。"""
    # 準備
    data = {"a": {"b": [{"c": 1}]}}
    # 実行
    result = get_field(data, "a.b[0].c")
    # 検証
    assert result == 1


@pytest.mark.parametrize("path", ["a.x", "a.b[3].c", "a.b.c"])
def test_get_field_when_missing(path: str) -> None:
    """たどれない（正常系）。"""
    # 準備
    data = {"a": {"b": [{"c": 1}]}}
    # 実行
    result = get_field(data, path)
    # 検証
    assert result is None


def test_get_field_when_selector() -> None:
    """要素を選んで取り出す（正常系）。"""
    # 準備
    data = {"tags": [{"name": "a", "main": True}, {"name": "b"}, "c"]}
    # 実行
    results = [
        get_field(data, "tags[].name"),
        get_field(data, "tags[main].name"),
        get_field({"tags": "x"}, "tags[].name"),
    ]
    # 検証
    assert results == [["a", "b"], ["a"], None]


@pytest.mark.parametrize(
    ("body_path", "expected"),
    [
        pytest.param("docs/a.md", True, id="markdown"),
        pytest.param("docs/B.MD", True, id="upper-case"),
        pytest.param("src/a.py", False, id="source-code"),
        pytest.param(None, False, id="no-body-file"),
    ],
)
def test_is_markdown_body(
    make_document: Callable[..., Document], body_path: str | None, expected: bool
) -> None:
    """本文のファイルの拡張子（正常系）。"""
    # 準備
    from dev_docs.features.documents.fields import is_markdown_body

    document = make_document(path="docs/x.md", body_path=body_path)
    # 実行
    result = is_markdown_body(document)
    # 検証
    assert result is expected


def test_with_row_metadata(
    make_document: Callable[..., Document], make_view: Callable[..., SourceView]
) -> None:
    """対応で値を取る（正常系）。"""
    # 準備
    view = make_view(
        documents=[
            DocumentRow(
                id="terms",
                paths=["terms/*.yaml"],
                schema={},
                metadata={"aliases": "synonyms"},
                alias_type="term",
            )
        ]
    )
    document = make_document(
        kind="terms",
        data={"synonyms": ["作業場所"], "status": "current"},
        metadata={"id": "doc-1", "name": "作業範囲"},
    )
    # 実行
    [found] = with_row_metadata(view, [document])
    # 検証
    assert found.metadata["aliases"] == ["作業場所"]
    assert found.metadata["status"] == "current"
    assert found.metadata["alias_type"] == "term"
    assert found.metadata["name"] == "作業範囲"


def test_with_row_metadata_when_row_missing(
    make_document: Callable[..., Document], make_view: Callable[..., SourceView]
) -> None:
    """行が無い種類（正常系）。"""
    # 準備
    view = make_view()
    document = make_document(kind="unknown", data={"status": "current"})
    # 実行
    [found] = with_row_metadata(view, [document])
    # 検証
    assert found == document
