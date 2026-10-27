"""`describe` の処理。"""

from __future__ import annotations

from dev_docs.features.describe.types import (
    DescribeRequest,
    KindSchemaResult,
    SourceGuideResult,
    SourceListResult,
)
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.sources.registry import SourceRegistry


def describe(
    request: DescribeRequest, *, registry: SourceRegistry, store: DocumentStore
) -> SourceListResult | SourceGuideResult | KindSchemaResult:
    """`describe` の要求を処理して結果を返す。"""
    raise NotImplementedError
