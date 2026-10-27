"""検索で使う項目の値と使える項目。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from dev_docs.features.documents.types import Document

COMPUTED_FIELDS = ("@chars", "@path", "@sections")
DATE_FIELDS = ("created", "updated")


def field_values(document: Document, field: str) -> list[Any]:
    """文書から項目の値を引き、比べられる値の並びにする。"""
    raise NotImplementedError


def known_fields(schemas: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """配信元の種類のスキーマから、条件・並べ替え・集計に使える項目の一覧を作る。"""
    raise NotImplementedError
