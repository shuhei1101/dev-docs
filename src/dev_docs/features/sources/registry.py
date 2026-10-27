"""配信元の一覧と読み直し。"""

from __future__ import annotations

import threading

from dev_docs.features.settings.types import TerminalConfig
from dev_docs.features.sources.service import load_source
from dev_docs.features.sources.types import ServedSource, SourceStatus

__all__ = ["SourceRegistry", "load_source"]


class SourceRegistry:
    """配信中の配信元と状態を持ち、読み直しで一覧ごと差し替える。"""

    def __init__(self) -> None:
        self._snapshot: tuple[dict[str, ServedSource], list[SourceStatus]] = ({}, [])
        self._reload_lock = threading.Lock()

    def reload(self, terminal: TerminalConfig) -> list[SourceStatus]:
        """端末の設定の全行を読み直し、一覧を差し替える。"""
        raise NotImplementedError

    def get(self, source_id: str) -> ServedSource:
        """配信中の配信元を ID で引く。"""
        raise NotImplementedError

    def served(self) -> list[ServedSource]:
        """配信中の配信元を `sources[]` の順に返す。"""
        raise NotImplementedError

    def statuses(self) -> list[SourceStatus]:
        """`sources[]` の順の状態を返す。"""
        raise NotImplementedError
