"""文書の検査の決まり。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dev_docs.shared.errors import Violation

SLUG_PATTERN = "[a-z0-9]+(?:-[a-z0-9]+)*"


def check_schema(data: Mapping[str, Any], schema: Mapping[str, Any]) -> list[Violation]:
    """文書の内容を種類の JSON Schema で検査する。"""
    raise NotImplementedError


def check_id_format(doc_id: str, fmt: str | None, *, kind: str) -> list[Violation]:
    """新しく作る文書の ID が `ids.format` に合うかを確かめる。"""
    raise NotImplementedError


def check_related(metadata: Mapping[str, Any], types: Sequence[str]) -> list[Violation]:
    """メタデータの `related` の各行が `to` と `related.types` の語の `type` を持つかを確かめる。"""
    raise NotImplementedError


def check_tags(metadata: Mapping[str, Any], tag_master: Mapping[str, str]) -> list[Violation]:
    """メタデータの `tags` がタグのマスターにあるかを確かめる。"""
    raise NotImplementedError
