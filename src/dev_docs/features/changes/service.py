"""`list_changes` の処理。"""

from __future__ import annotations

from dev_docs.features.changes.types import ChangesRequest, ChangesResult
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.sources.registry import SourceRegistry


def list_changes(
    request: ChangesRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    seen: SeenStore,
) -> ChangesResult:
    """`list_changes` の要求を処理して変更の結果を返す。"""
    raise NotImplementedError
