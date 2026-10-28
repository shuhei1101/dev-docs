"""表の列の設定。"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from dev_docs.shared.files import replace_file

logger = logging.getLogger(__name__)

COLUMNS_DIR = "columns"


class ColumnSettings:
    """配信元・表ごとの隠す列を `state_dir` の JSON に読み書きする。"""

    def __init__(self, dir: Path) -> None:
        self.dir = dir
        self._lock = threading.Lock()

    def _path(self, source_id: str) -> Path:
        """配信元の列の設定のファイルを返す。"""
        return self.dir / f"{source_id}.json"

    def _read(self, source_id: str) -> dict[str, list[str]]:
        """ファイルを読む（無い・読めないときは空）。"""
        path = self._path(source_id)
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("最上位が辞書ではありません")
            return {str(key): [str(item) for item in value] for key, value in data.items()}
        except (OSError, ValueError, TypeError) as error:
            logger.warning("列の設定を読めない（%s・%s）", path, error)
            return {}

    def get(self, source_id: str) -> dict[str, list[str]]:
        """配信元の表のキー → 隠す列を返す。"""
        return self._read(source_id)

    def save(self, source_id: str, table: str, hidden: list[str]) -> None:
        """1 つの表の隠す列を書き、他の表の設定は残す。"""
        with self._lock:
            settings = self._read(source_id)
            if hidden:
                settings[table] = list(dict.fromkeys(hidden))
            else:
                settings.pop(table, None)
            replace_file(
                self._path(source_id), json.dumps(settings, ensure_ascii=False, indent=2) + "\n"
            )
