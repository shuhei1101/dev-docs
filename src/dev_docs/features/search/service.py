"""`search_docs` の処理。"""

from __future__ import annotations

from datetime import date

from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.search.types import SearchRequest, SearchResult
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.validation.service import DocumentChecker


def search_docs(
    request: SearchRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    checker: DocumentChecker,
    seen: SeenStore,
    today: date | None = None,
) -> SearchResult:
    """`search_docs` の要求を処理して検索の結果を返す。"""
    raise NotImplementedError
