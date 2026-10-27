"""内容のハッシュ（文書のバージョン）。"""

from __future__ import annotations

from typing import Any

VERSION_LENGTH = 6


def content_hash(data: str | bytes) -> str:
    """内容の SHA-256 の先頭 VERSION_LENGTH 桁を返す。"""
    raise NotImplementedError


def value_hash(value: Any) -> str:
    """項目の値を正規化した JSON にしてハッシュを取る。"""
    raise NotImplementedError
