from __future__ import annotations

from typing import Any

import pytest

from dev_docs.features.sources.types import DocumentTable
from dev_docs.features.write import apply as apply_module
from dev_docs.features.write.apply import apply_operation
from dev_docs.features.write.types import Operation, TextEdit
from dev_docs.shared.errors import InvalidArgumentError


def _decisions_table(**overrides: Any) -> DocumentTable:
    """共通のキーと列名の対応を持つ文書の行を返す。"""
    values: dict[str, Any] = {
        "id": "decisions",
        "paths": ["decisions/*.yaml"],
        "schema_path": "schemas/decision.schema.yaml",
        "metadata": {"name": "title", "description": "meta.summary"},
    }
    values.update(overrides)
    return DocumentTable(**values)


def test_apply_operation() -> None:
    """部分更新の組み合わせ（正常系）。"""
    # 準備
    current = {"a": {"b": 1, "c": 2}, "tags": ["a", "b"], "d": "x"}
    operation = Operation(
        op="update",
        id="doc-1",
        expected_version="v1",
        set={"a": {"b": 9}},
        unset=["d"],
        add_to={"tags": ["c"]},
        remove_from={"tags": ["a"]},
    )
    # 実行
    result = apply_operation(current, operation)
    # 検証
    assert result == {"a": {"b": 9, "c": 2}, "tags": ["b", "c"]}
    assert current == {"a": {"b": 1, "c": 2}, "tags": ["a", "b"], "d": "x"}


def test_apply_operation_when_text_edit_ambiguous() -> None:
    """一致が 2 か所（異常系）。"""
    # 準備
    current = {"description": "aXbXc"}
    operation = Operation(
        op="update",
        id="doc-1",
        expected_version="v1",
        text_edits=[TextEdit(field="description", old="X", new="Y")],
    )
    # 実行・検証
    with pytest.raises(InvalidArgumentError) as exc_info:
        apply_operation(current, operation)
    assert exc_info.value.violations[0].path == "text_edits[0].old"
    assert "2" in exc_info.value.violations[0].fix


def test_apply_operation_when_replace() -> None:
    """置き換え（正常系）。"""
    # 準備
    operation = Operation(op="replace", id="doc-1", expected_version="v1", data={"a": 3})
    # 実行
    result = apply_operation({"a": 1, "b": 2}, operation)
    # 検証
    assert result == {"a": 3}


def test_to_columns() -> None:
    """update の項目のパスを読み替える（正常系）。"""
    # 準備
    operation = Operation(
        op="update",
        id="d1",
        expected_version="v1",
        set={"name": "A", "tags": ["x"]},
        unset=["description"],
        text_edits=[TextEdit(field="name", old="a", new="b")],
    )
    # 実行
    result = apply_module.to_columns(operation, _decisions_table(), index=0)
    # 検証
    assert result.set == {"title": "A", "tags": ["x"]}
    assert result.unset == ["meta.summary"]
    assert result.text_edits[0].field == "title"
    assert operation.set == {"name": "A", "tags": ["x"]}


def test_to_columns_when_data() -> None:
    """create の data を列へ入れる（正常系）。"""
    # 準備
    operation = Operation(
        op="create",
        kind="decisions",
        data={"name": "A", "description": "d", "tags": ["x"]},
    )
    # 実行
    result = apply_module.to_columns(operation, _decisions_table(), index=0)
    # 検証
    assert result.data == {"title": "A", "meta": {"summary": "d"}, "tags": ["x"]}


@pytest.mark.parametrize(
    ("metadata", "values"),
    [
        pytest.param(
            {"name": "title", "description": "meta.summary"}, {"title": "A"}, id="column-name"
        ),
        pytest.param({}, {"name": "A"}, id="no-mapping"),
    ],
)
def test_to_columns_when_column_name(metadata: dict[str, str], values: dict[str, str]) -> None:
    """列名をそのまま渡す（正常系）。"""
    # 準備
    operation = Operation(op="update", id="d1", expected_version="v1", set=values)
    # 実行
    result = apply_module.to_columns(operation, _decisions_table(metadata=metadata), index=0)
    # 検証
    assert result.set == values


def test_to_columns_when_both() -> None:
    """共通のキーと列名を両方渡す（異常系）。"""
    # 準備
    operation = Operation(
        op="update", id="d1", expected_version="v1", set={"name": "a", "title": "b"}
    )
    # 実行・検証
    with pytest.raises(InvalidArgumentError) as exc_info:
        apply_module.to_columns(operation, _decisions_table(), index=2)
    assert exc_info.value.violations[0].path == "operations[2].set.name"
    assert "title" in exc_info.value.violations[0].rule
