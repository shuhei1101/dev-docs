"""配信元の一覧と読み直し。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from dev_docs.features.history.query import resolve_ref
from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.features.sources.service import load_source
from dev_docs.features.sources.types import ServedSource, SourceStatus
from dev_docs.shared.errors import (
    DevDocsError,
    SourceNotServedError,
    UnknownSourceError,
    Violation,
)

logger = logging.getLogger(__name__)

__all__ = ["SourceRegistry", "load_source"]


class SourceRegistry:
    """配信中の配信元と状態を持ち、読み直しで一覧ごと差し替える。"""

    def __init__(self, on_rebuilt: Callable[[ServedSource], None] | None = None) -> None:
        self._snapshot: tuple[dict[str, ServedSource], list[SourceStatus]] = ({}, [])
        self._reload_lock = threading.Lock()
        self._entries: dict[str, tuple[SourceEntry, int]] = {}
        self._on_rebuilt = on_rebuilt

    def reload(self, terminal: TerminalConfig) -> list[SourceStatus]:
        """端末の設定の全行を読み直し、一覧を差し替える。"""
        with self._reload_lock:
            sources: dict[str, ServedSource] = {}
            statuses: list[SourceStatus] = []
            entries: dict[str, tuple[SourceEntry, int]] = {}
            for index, entry in enumerate(terminal.sources):
                served, status = load_source(entry, index=index)
                # 配信する配信元の ID が先の行と重なるときは、後の行を外す
                if served is not None and served.id in sources:
                    status = SourceStatus(
                        id=served.id,
                        index=index,
                        status="not_served",
                        config=tuple(entry.config),
                        errors=[
                            Violation(
                                path=f"sources[{index}].id",
                                rule=f"{served.id} は既に使われています",
                                fix="sources[].id を別の値にしてください",
                            )
                        ],
                    )
                    served = None
                if served is not None:
                    sources[served.id] = served
                    entries[served.id] = (entry, index)
                statuses.append(status)
            self._entries = entries
            self._snapshot = (sources, statuses)
            logger.info(
                "配信元を読み直した（配信中: %s・外した数: %s）",
                list(sources),
                sum(1 for status in statuses if status.status == "not_served"),
            )
            return statuses

    def get(self, source_id: str) -> ServedSource:
        """配信中の配信元を ID で引く。"""
        sources, statuses = self._snapshot
        if source_id in sources:
            return self._refresh(sources[source_id])
        for status in statuses:
            if status.id == source_id and status.status in ("not_served", "disabled"):
                disabled = status.status == "disabled"
                reason = (
                    "無効です"
                    if disabled
                    else "; ".join(f"{v.path}: {v.rule}" for v in status.errors)
                )
                raise SourceNotServedError(
                    message=f"{source_id} は配信していません（{reason}）",
                    violations=status.errors,
                    disabled=disabled,
                )
        raise UnknownSourceError(message=f"配信元 {source_id} はありません", source_id=source_id)

    def _current_commit(self, source: ServedSource) -> str | None:
        """配信元の `default_ref` の今の commit。解けなければ `None`。"""
        if source.repo_root is None:
            return None
        default_ref = source.config.default_ref
        try:
            return resolve_ref(source.repo_root, default_ref, date_base=default_ref).commit
        except DevDocsError:
            return None

    def _refresh(self, source: ServedSource) -> ServedSource:
        """`default_ref` が進んでいれば、その配信元だけを組み立て直して差し替える。"""
        if source.config_commit is None:
            return source
        current = self._current_commit(source)
        if current is None or current == source.config_commit:
            return source
        with self._reload_lock:
            sources, statuses = self._snapshot
            latest = sources.get(source.id, source)
            if latest.config_commit == current or source.id not in self._entries:
                return latest
            entry, index = self._entries[source.id]
            served, status = load_source(entry, index=index)
            next_sources = dict(sources)
            if served is None:
                next_sources.pop(source.id, None)
            else:
                next_sources[source.id] = served
            next_statuses = [status if item.index == index else item for item in statuses]
            self._snapshot = (next_sources, next_statuses)
            logger.info(
                "default_ref が進んだので配信元を組み立て直した（%s・%s → %s）",
                source.id,
                source.config_commit,
                current,
            )
            if served is not None and self._on_rebuilt is not None:
                self._on_rebuilt(served)
        if served is None:
            return self.get(source.id)
        return served

    def served(self) -> list[ServedSource]:
        """配信中の配信元を `sources[]` の順に返す。"""
        sources, statuses = self._snapshot
        return [
            sources[status.id]
            for status in statuses
            if status.status == "serving" and status.id in sources
        ]

    def statuses(self) -> list[SourceStatus]:
        """`sources[]` の順の状態を返す。"""
        return self._snapshot[1]
