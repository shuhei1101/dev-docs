"""スキーマ駆動の Markdown への変換。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dev_docs.features.documents.types import Document

MAX_HEADING_LEVEL = 6


def schema_to_markdown(document: Document, schema: Mapping[str, Any]) -> str:
    """YAML の文書をスキーマの `x-heading`・`x-shape`・`x-key`・`x-diagram`・`title` に沿って Markdown にする。"""
    raise NotImplementedError


def render_table(
    rows: Sequence[Mapping[str, Any]], item_schema: Mapping[str, Any], *, table_key: str
) -> str:
    """オブジェクトのリストを、mdmark の表のマーカーつきの Markdown の表にする。"""
    raise NotImplementedError
