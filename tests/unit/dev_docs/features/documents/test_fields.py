from __future__ import annotations

from typing import Any

import pytest

from dev_docs.features.documents.fields import (
    apply_defaults,
    delete_field,
    get_field,
    parse_field_path,
    resolve_metadata,
    set_field,
)
from dev_docs.features.sources.types import DocumentDefaults, DocumentTable, MetadataMapping
from dev_docs.shared.errors import InvalidArgumentError


def test_parse_field_path() -> None:
    """キーと位置（正常系）。"""
    # 実行
    result = parse_field_path("a.b[0][1].c")
    # 検証
    assert result == ["a", "b", 0, 1, "c"]


@pytest.mark.parametrize(
    "path", [pytest.param("a..b", id="empty-key"), pytest.param("a[x]", id="bad-index")]
)
def test_parse_field_path_when_invalid(path: str) -> None:
    """空のキーと数字でない位置（異常系）。"""
    # 実行・検証
    with pytest.raises(InvalidArgumentError) as exc_info:
        parse_field_path(path)
    assert exc_info.value.violations[0].path == path


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


def test_set_field() -> None:
    """途中の辞書を作る（正常系）。"""
    # 準備
    data: dict[str, Any] = {}
    # 実行
    set_field(data, "a.b.c", 1)
    # 検証
    assert data == {"a": {"b": {"c": 1}}}


def test_set_field_when_append() -> None:
    """末尾へ追加（正常系）。"""
    # 準備
    data: dict[str, Any] = {"a": [1]}
    # 実行
    set_field(data, "a[1]", 2)
    # 検証
    assert data == {"a": [1, 2]}


def test_set_field_when_type_mismatch() -> None:
    """途中が文字列（異常系）。"""
    # 準備
    data: dict[str, Any] = {"a": "x"}
    # 実行・検証
    with pytest.raises(InvalidArgumentError):
        set_field(data, "a.b", 1)


def test_set_field_when_out_of_range() -> None:
    """飛んだ位置（異常系）。"""
    # 準備
    data: dict[str, Any] = {"a": [1]}
    # 実行・検証
    with pytest.raises(InvalidArgumentError):
        set_field(data, "a[3]", 2)


def test_delete_field() -> None:
    """キーと位置（正常系）。"""
    # 準備
    data: dict[str, Any] = {"a": {"b": 1}, "c": [1, 2]}
    # 実行
    key_deleted = delete_field(data, "a.b")
    index_deleted = delete_field(data, "c[0]")
    # 検証
    assert key_deleted is True
    assert index_deleted is True
    assert data == {"a": {}, "c": [2]}


def test_delete_field_when_missing() -> None:
    """無い値（正常系）。"""
    # 準備
    data: dict[str, Any] = {}
    # 実行
    result = delete_field(data, "a.b")
    # 検証
    assert result is False
    assert data == {}


def test_resolve_metadata() -> None:
    """対応と既定の ref（正常系）。"""
    # 準備
    table = DocumentTable(
        id="rules",
        type="yaml",
        paths=["docs/*.yaml"],
        metadata={
            "name": MetadataMapping(type="ref", field="title"),
            "alias_type": MetadataMapping(type="custom", value="term"),
        },
    )
    data = {"id": "a", "title": "A", "tags": ["x"]}
    # 実行
    result = resolve_metadata(data, table)
    # 検証
    assert result == {"id": "a", "name": "A", "tags": ["x"], "alias_type": "term"}


def test_resolve_metadata_when_nested_field() -> None:
    """入れ子の列（正常系）。"""
    # 準備
    table = DocumentTable(
        id="rules",
        type="yaml",
        paths=["docs/*.yaml"],
        metadata={"description": MetadataMapping(type="ref", field="meta.summary")},
    )
    data = {"meta": {"summary": "s"}}
    # 実行
    result = resolve_metadata(data, table)
    # 検証
    assert result["description"] == "s"


def test_apply_defaults() -> None:
    """和集合と上書き（正常系）。"""
    # 準備
    defaults = [
        DocumentDefaults(paths=["src/**"], tags=["a"], status="draft"),
        DocumentDefaults(paths=["src/x/**"], tags=["b"]),
    ]
    metadata = {"tags": ["a", "c"], "status": "done"}
    # 実行
    result = apply_defaults(metadata, defaults, "src/x/y.md")
    # 検証
    assert result == {"tags": ["a", "b", "c"], "status": "done"}


def test_apply_defaults_when_not_matched() -> None:
    """当たらない行（正常系）。"""
    # 準備
    defaults = [DocumentDefaults(paths=["docs/**"], tags=["a"])]
    # 実行
    result = apply_defaults({}, defaults, "src/y.md")
    # 検証
    assert result == {}
