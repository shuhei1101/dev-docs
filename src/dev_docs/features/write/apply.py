"""項目の操作を当てる。"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any, cast

from dev_docs.features.documents.fields import delete_field, get_field, set_field
from dev_docs.features.sources.types import DocumentTable
from dev_docs.features.write.types import Operation
from dev_docs.shared.errors import InvalidArgumentError, Violation


def _merge(target: MutableMapping[str, Any], value: Mapping[str, Any]) -> None:
    """オブジェクトは今の値へ再帰でマージし、配列とスカラーは置き換える。"""
    for key, item in value.items():
        if isinstance(item, Mapping) and isinstance(target.get(key), MutableMapping):
            _merge(target[key], item)
        else:
            target[key] = copy.deepcopy(item)


def _set(content: MutableMapping[str, Any], path: str, value: Any) -> None:
    """項目のパスへ値を入れる（オブジェクトなら今の値へマージする）。"""
    existing = get_field(content, path)
    if isinstance(value, Mapping) and isinstance(existing, MutableMapping):
        _merge(existing, value)
    else:
        set_field(content, path, copy.deepcopy(value))


def _violation(path: str, rule: str, fix: str = "") -> Violation:
    """操作を当てられない違反 1 件を作る。"""
    return Violation(path=path, rule=rule, fix=fix)


def apply_operation(current: Mapping[str, Any] | None, operation: Operation) -> dict[str, Any]:
    """文書の内容に 1 件の操作を当てた新しい内容を返す。"""
    if operation.op in ("create", "replace"):
        return copy.deepcopy(operation.data or {})
    content = cast("dict[str, Any]", copy.deepcopy(current if current is not None else {}))
    violations: list[Violation] = []
    for path, value in operation.set.items():
        try:
            _set(content, path, value)
        except InvalidArgumentError as error:
            violations.extend(
                _violation(f"set.{path}", violation.rule) for violation in error.violations
            )
    for path in operation.unset:
        delete_field(content, path)
    for path, values in operation.add_to.items():
        existing = get_field(content, path)
        if existing is None:
            set_field(content, path, [])
            existing = get_field(content, path)
        if not isinstance(existing, list):
            violations.append(_violation(f"add_to.{path}", "配列ではない項目へは追加できません"))
            continue
        existing.extend(copy.deepcopy(item) for item in values)
    for path, values in operation.remove_from.items():
        existing = get_field(content, path)
        if existing is None:
            continue
        if not isinstance(existing, list):
            violations.append(
                _violation(f"remove_from.{path}", "配列ではない項目からは削除できません")
            )
            continue
        existing[:] = [item for item in existing if item not in values]
    for index, edit in enumerate(operation.text_edits):
        text = get_field(content, edit.field)
        prefix = f"text_edits[{index}]"
        if not isinstance(text, str):
            violations.append(
                _violation(f"{prefix}.field", "文字列ではない項目は置き換えられません")
            )
            continue
        count = text.count(edit.old) if edit.old else 0
        if count == 0 or (count > 1 and not edit.replace_all):
            violations.append(
                _violation(
                    f"{prefix}.old",
                    f"old の一致が {count} か所です",
                    f"一致が 1 か所になるよう前後の文字を含めるか、replace_all を true にしてください"
                    f"（一致 {count} 件）",
                )
            )
            continue
        set_field(content, edit.field, text.replace(edit.old, edit.new))
    if violations:
        raise InvalidArgumentError(message="操作を当てられません", violations=violations)
    return content


HEAD_PATTERN = re.compile(r"^([^.\[\]]+)(.*)$")


def _to_column(path: str, metadata: Mapping[str, str]) -> str:
    """項目のパスの先頭のキーが共通のキーなら、列名のパスに置き換える。"""
    matched = HEAD_PATTERN.match(path)
    if matched is None or matched.group(1) not in metadata:
        return path
    return metadata[matched.group(1)] + matched.group(2)


def _check_overlap(
    paths: Iterable[str], metadata: Mapping[str, str], *, item: str, index: int
) -> None:
    """共通のキーと、その列名を同じ項目に両方渡していないかを確かめる。"""
    given = list(paths)
    violations = [
        Violation(
            path=f"operations[{index}].{item}.{path}",
            rule=f"{path} と {_to_column(path, metadata)} は同じ列を指します",
            fix="どちらか 1 つだけを渡してください",
        )
        for path in given
        if (column := _to_column(path, metadata)) != path and column in given
    ]
    if violations:
        raise InvalidArgumentError(
            message=f"引数が正しくありません: {len(violations)} 件", violations=violations
        )


def to_columns(operation: Operation, table: DocumentTable, *, index: int) -> Operation:
    """操作のキーのうち、種類の行の `metadata` に書いた共通のキーを列名へ読み替えた操作を返す。"""
    metadata = table.metadata
    if not metadata:
        return operation
    for item in ("set", "add_to", "remove_from"):
        _check_overlap(getattr(operation, item), metadata, item=item, index=index)
    _check_overlap(operation.unset, metadata, item="unset", index=index)
    update: dict[str, Any] = {
        "set": {_to_column(path, metadata): value for path, value in operation.set.items()},
        "add_to": {_to_column(path, metadata): value for path, value in operation.add_to.items()},
        "remove_from": {
            _to_column(path, metadata): value for path, value in operation.remove_from.items()
        },
        "unset": [_to_column(path, metadata) for path in operation.unset],
        "text_edits": [
            edit.model_copy(update={"field": _to_column(edit.field, metadata)})
            for edit in operation.text_edits
        ],
    }
    if operation.data is not None:
        _check_overlap(operation.data, metadata, item="data", index=index)
        data: dict[str, Any] = {}
        for key, value in operation.data.items():
            if key in metadata:
                set_field(data, metadata[key], copy.deepcopy(value))
            else:
                data[key] = copy.deepcopy(value)
        update["data"] = data
    return operation.model_copy(update=update)
