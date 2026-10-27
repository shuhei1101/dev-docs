"""git の子プロセスでの実行。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

GIT_TIMEOUT_SEC = 8
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"}


class GitError(Exception):
    """git が 0 以外で終わったか待ち時間の上限を超えたこと。"""

    def __init__(
        self, args_: list[str], returncode: int, stderr: str, *, timed_out: bool = False
    ) -> None:
        super().__init__(stderr)
        self.args_ = args_
        self.returncode = returncode
        self.stderr = stderr
        self.timed_out = timed_out


def run_git(args: Sequence[str], *, cwd: Path, binary: bool = False) -> str | bytes:
    """git を子プロセスで 1 回呼び、標準出力を返す。"""
    raise NotImplementedError


def repo_root(path: Path) -> Path | None:
    """フォルダが Git の作業ツリーの中なら、その直下を返す。"""
    raise NotImplementedError
