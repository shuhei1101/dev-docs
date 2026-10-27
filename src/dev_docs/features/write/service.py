"""`write_docs`・`delete_docs` の処理。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.seen.types import LastRead
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.validation.service import DocumentChecker
from dev_docs.features.write.locks import SourceLocks
from dev_docs.features.write.types import DeleteRequest, DeleteResult, WriteRequest, WriteResult


def check_version(
    document: Document, expected: str | Mapping[str, str], *, last_read: LastRead | None
) -> None:
    """`expected_version` が今の文書と同じかを確かめる。"""
    raise NotImplementedError


def write_docs(
    request: WriteRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    checker: DocumentChecker,
    seen: SeenStore,
    locks: SourceLocks,
    timeout_sec: float,
    now: datetime | None = None,
) -> WriteResult:
    """`write_docs` の要求を処理して書き込みの結果を返す。"""
    raise NotImplementedError


def delete_docs(
    request: DeleteRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    checker: DocumentChecker,
    locks: SourceLocks,
    timeout_sec: float,
) -> DeleteResult:
    """`delete_docs` の要求を処理して削除の結果を返す。"""
    raise NotImplementedError
