"""配信元の一覧と読み直し。"""

from __future__ import annotations

import logging
import threading

from dev_docs.features.settings.types import TerminalConfig
from dev_docs.features.sources.service import load_source
from dev_docs.features.sources.types import ServedSource, SourceStatus
from dev_docs.shared.errors import SourceNotServedError, UnknownSourceError, Violation

logger = logging.getLogger(__name__)

__all__ = ["SourceRegistry", "load_source"]


class SourceRegistry:
    """配信中の配信元と状態を持ち、読み直しで一覧ごと差し替える。"""

    def __init__(self) -> None:
        self._snapshot: tuple[dict[str, ServedSource], list[SourceStatus]] = ({}, [])
        self._reload_lock = threading.Lock()

    def reload(self, terminal: TerminalConfig) -> list[SourceStatus]:
        """端末の設定の全行を読み直し、一覧を差し替える。"""
        with self._reload_lock:
            sources: dict[str, ServedSource] = {}
            statuses: list[SourceStatus] = []
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
                statuses.append(status)
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
            return sources[source_id]
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
