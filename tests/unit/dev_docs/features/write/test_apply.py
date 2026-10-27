from __future__ import annotations

import pytest

from dev_docs.features.write.apply import apply_operation
from dev_docs.features.write.types import Operation, TextEdit
from dev_docs.shared.errors import InvalidArgumentError


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
