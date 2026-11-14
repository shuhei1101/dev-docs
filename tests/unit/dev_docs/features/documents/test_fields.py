from __future__ import annotations

from collections.abc import Callable

import pytest

from dev_docs.features.documents.fields import get_field, parse_field_path
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
