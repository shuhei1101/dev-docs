"""リビジョンの書き出し。"""

from __future__ import annotations

import threading
from pathlib import Path

from dev_docs.integrations.git import run_git

SNAPSHOT_KEEP = 20

__all__ = ["SNAPSHOT_KEEP", "SnapshotStore", "run_git"]


class SnapshotStore:
    """commit のファイルを `state_dir` の下に書き出し、同じ commit は書き出したフォルダを返す。"""

    def __init__(self, dir: Path, keep: int = SNAPSHOT_KEEP) -> None:
        self.dir = dir
        self.keep = keep
        self._locks: dict[Path, threading.Lock] = {}

    def checkout(self, repo_root: Path, commit: str) -> Path:
        """commit のファイルを書き出したフォルダを返す。"""
        raise NotImplementedError
