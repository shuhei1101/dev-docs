"""`trace_related` の処理。"""

from __future__ import annotations

from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.related.types import RelatedRequest, RelatedResult
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.sources.registry import SourceRegistry


def trace_related(
    request: RelatedRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    seen: SeenStore,
) -> RelatedResult:
    """`trace_related` の要求を処理して関連のたどりの結果を返す。"""
    raise NotImplementedError
