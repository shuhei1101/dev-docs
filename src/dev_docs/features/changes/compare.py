"""変わったキーの比べ方。"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

MATCH_KEYS = ("id", "name")


def _match_key(items: list[Any]) -> str | None:
    """要素を突き合わせるキー（全ての要素が持つ `id` か `name`）を返す。"""
    if not items or not all(isinstance(item, Mapping) for item in items):
        return None
    for key in MATCH_KEYS:
        values = [item.get(key) for item in items]
        if all(value is not None for value in values) and len(set(map(str, values))) == len(values):
            return key
    return None


def _walk(before: Any, after: Any, path: str, found: dict[str, tuple[Any, Any]]) -> None:
    """2 つの値を再帰で比べ、違うパスを `found` に入れる。"""
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        keys = [*after, *(key for key in before if key not in after)]
        for key in keys:
            _walk(before.get(key), after.get(key), f"{path}.{key}" if path else str(key), found)
        return
    if isinstance(before, list) and isinstance(after, list):
        key = _match_key([*before, *after]) if before or after else None
        # 前後のどちらかが空でも、残る側のキーで突き合わせられる
        key = key or _match_key(before) or _match_key(after)
        if key is not None:
            by_before = {str(item[key]): item for item in before}
            by_after = {str(item[key]): item for item in after}
            for name in [*by_after, *(name for name in by_before if name not in by_after)]:
                _walk(by_before.get(name), by_after.get(name), f"{path}[{name}]", found)
            return
    if before != after:
        found[path] = (before, after)


def changed_keys(
    before: Mapping[str, Any], after: Mapping[str, Any], *, ignore: Collection[str] = ()
) -> dict[str, tuple[Any, Any]]:
    """2 つの内容を比べ、変わったキーのパスと前後の値を返す。"""
    found: dict[str, tuple[Any, Any]] = {}
    keys = [*after, *(key for key in before if key not in after)]
    for key in keys:
        if key in ignore:
            continue
        _walk(before.get(key), after.get(key), str(key), found)
    return found
