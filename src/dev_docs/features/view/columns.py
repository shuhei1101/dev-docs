"""表の列の設定。"""

from __future__ import annotations

import threading
from pathlib import Path

COLUMNS_DIR = "columns"


class ColumnSettings:
    """配信元・表ごとの隠す列を `state_dir` の JSON に読み書きする。"""

    def __init__(self, dir: Path) -> None:
        self.dir = dir
        self._lock = threading.Lock()

    def get(self, source_id: str) -> dict[str, list[str]]:
        """配信元の表のキー → 隠す列を返す。"""
        raise NotImplementedError

    def save(self, source_id: str, table: str, hidden: list[str]) -> None:
        """1 つの表の隠す列を書き、他の表の設定は残す。"""
        raise NotImplementedError
