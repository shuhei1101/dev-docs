"""`ids.format` からの ID の作成。"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

ID_FALLBACK_SLUG = "doc"


def generate_id(fmt: str, *, kind: str, data: Mapping[str, Any], existing: Collection[str]) -> str:
    """`ids.format` の `{kind}`・`{slug}` を埋めて、配信元の中で重ならない ID を作る。"""
    raise NotImplementedError
