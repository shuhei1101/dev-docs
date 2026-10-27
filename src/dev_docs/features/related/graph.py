"""`related` のたどり。"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from dev_docs.features.documents.types import Document
from dev_docs.features.related.types import RelatedLink


def related_links(document: Document) -> list[RelatedLink]:
    """文書のメタデータの `related` を関連の行の並びにする。"""
    raise NotImplementedError


def walk_related(
    start: Sequence[Document],
    documents: Mapping[str, Document],
    *,
    depth: int,
    direction: Literal["out", "in", "both"],
    resolve_other: Callable[[str, str], Document | None],
) -> tuple[list[tuple[Document, int, str, str, Literal["out", "in"]]], list[str]]:
    """起点から幅優先で `related` をたどり、たどった文書を深さつきで返す。"""
    raise NotImplementedError
