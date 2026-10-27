"""文書の検査をまとめて通す。"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Literal

from dev_docs.features.access.types import Target
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.integrations.scripts import run_script
from dev_docs.shared.errors import Violation

VALIDATOR_ON_READ_CACHE = 4096

__all__ = ["VALIDATOR_ON_READ_CACHE", "DocumentChecker", "run_script"]


class DocumentChecker:
    """1 件の文書に全ての検査を通し、違反をまとめて返す。"""

    def __init__(self, store: DocumentStore, timeout_sec: float) -> None:
        self.store = store
        self.timeout_sec = timeout_sec
        self._read_cache: OrderedDict[tuple[str, str, str, str], list[Violation]] = OrderedDict()
        self._lock = threading.Lock()

    def check(
        self,
        target: Target,
        document: Document,
        *,
        on: Literal["read", "write"],
        new: bool = False,
    ) -> list[Violation]:
        """スキーマ・ID の形・関連の種類・タグ・`validators[]` を順に通す。"""
        raise NotImplementedError

    def clear(self) -> None:
        """読み取りの結果の控えを捨てる。"""
        raise NotImplementedError
