"""文書のキャッシュと ID の引き当て。"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from dev_docs.features.access.types import Target
from dev_docs.features.documents.loader import collect_files, load_file
from dev_docs.features.documents.types import Document, LoadProblem, LoadResult
from dev_docs.features.history.snapshot import SnapshotStore
from dev_docs.features.history.types import FileDates

CANDIDATE_COUNT = 5
CANDIDATE_CUTOFF = 0.6

__all__ = [
    "CANDIDATE_COUNT",
    "CANDIDATE_CUTOFF",
    "DocumentStore",
    "collect_files",
    "load_file",
]


class DocumentStore:
    """読む場所ごとに文書を集め、ファイルごとに結果をキャッシュする。"""

    def __init__(self, snapshots: SnapshotStore) -> None:
        self.snapshots = snapshots
        self._files: dict[tuple[Path, str], tuple[int, int, list[Document], list[LoadProblem]]] = {}
        self._schemas: dict[Path, tuple[int, int, dict[str, Any]]] = {}
        self._dates: dict[tuple[Path, str], dict[str, FileDates]] = {}
        self._lock = threading.Lock()

    def load(self, target: Target, *, kinds: Sequence[str] | None = None) -> LoadResult:
        """読む場所の文書を、文書の行ごとに集めて返す。"""
        raise NotImplementedError

    def get(
        self, target: Target, ids: Sequence[str], *, kinds: Sequence[str] | None = None
    ) -> list[Document]:
        """ID の並びの順に文書を返す。"""
        raise NotImplementedError

    def schema(self, target: Target, kind: str) -> dict[str, Any]:
        """読む場所に合わせた種類のスキーマを返す。"""
        raise NotImplementedError

    def invalidate(self, paths: Iterable[Path]) -> None:
        """書き込んだファイルのキャッシュを捨てる。"""
        raise NotImplementedError

    def clear(self) -> None:
        """全てのキャッシュを捨てる。"""
        raise NotImplementedError
