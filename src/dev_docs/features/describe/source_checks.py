"""配信元ごとの検査の結果。"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from dev_docs.features.documents.store import DocumentStore, check_sync
from dev_docs.features.documents.types import SyncReport
from dev_docs.features.sources.types import ServedSource
from dev_docs.features.view.nav import nav_warnings
from dev_docs.shared.errors import Violation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceCheck:
    """1 つの配信元の同期のずれと `nav` の警告。"""

    report: SyncReport
    nav: list[Violation]


class SourceChecks:
    """配信元の ID ごとに最後の検査の結果を持つ。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._results: dict[str, SourceCheck] = {}

    def refresh(self, store: DocumentStore, source: ServedSource) -> SourceCheck:
        """配信元を検査し、結果を持って返す。"""
        # 配信元のフォルダをたどる検査はロックの外で流す
        check = SourceCheck(report=check_sync(store, source), nav=nav_warnings(store, source))
        with self._lock:
            self._results[source.id] = check
        return check

    def get(self, source_id: str) -> SourceCheck | None:
        """配信元の ID の最後の検査の結果を返す（まだ検査していなければ `None`）。"""
        with self._lock:
            return self._results.get(source_id)

    def refresh_later(self, store: DocumentStore, sources: list[ServedSource]) -> threading.Thread:
        """配信元を裏のスレッドで検査し直し、待たずに戻る。"""

        def work() -> None:
            for source in sources:
                try:
                    self.refresh(store, source)
                except Exception:
                    logger.exception("配信元の検査に失敗した（%s）", source.id)

        thread = threading.Thread(target=work, name="dev-docs-source-checks", daemon=True)
        thread.start()
        return thread
