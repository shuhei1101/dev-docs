"""種類のスキーマの `$ref` の解決。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


def resolve_schema_refs(schema: Mapping[str, Any], base: Path) -> dict[str, Any]:
    """種類のスキーマの `$ref` を参照先の中身で置き換えたスキーマを返す。"""
    raise NotImplementedError
