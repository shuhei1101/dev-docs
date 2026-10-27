"""内容の比較。"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any


def changed_keys(
    before: Mapping[str, Any], after: Mapping[str, Any], *, ignore: Collection[str] = ()
) -> dict[str, tuple[Any, Any]]:
    """2 つの内容を比べ、変わったキーのパスと前後の値を返す。"""
    raise NotImplementedError


def diff_lines(before: str, after: str) -> str:
    """2 つの文字列の違う行を、git と同じ `-`・`+` の行にする。"""
    raise NotImplementedError
