"""配信元のスクリプトの制限時間つきの実行。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

STDERR_TAIL_LINES = 5
KILL_GRACE_SEC = 2


@dataclass(frozen=True, slots=True, kw_only=True)
class ScriptResult:
    """終了コード 0 で終えたスクリプトの標準出力と標準エラー。"""

    stdout: str
    stderr: str


class ScriptError(Exception):
    """スクリプトを動かせない・失敗したことを表す基底。"""

    def __init__(
        self, run: list[str], reason: str, *, exit_code: int | None = None, stdout: str = ""
    ) -> None:
        super().__init__(reason)
        self.run = run
        self.reason = reason
        self.exit_code = exit_code
        self.stdout = stdout


class ScriptNotFoundError(ScriptError):
    """コマンドが見つからない。"""


class ScriptTimeoutError(ScriptError):
    """制限時間を超えた。"""


class ScriptFailedError(ScriptError):
    """終了コードが 0 以外。"""


def run_script(
    run: Sequence[str],
    *,
    cwd: Path,
    stdin: str = "",
    args: Sequence[str] = (),
    timeout_sec: float,
) -> ScriptResult:
    """コマンドを配信元の直下で動かし、制限時間を超えたら止める。"""
    raise NotImplementedError


def check_runnable(run: Sequence[str], *, cwd: Path) -> list[str]:
    """コマンドの先頭と、配信元の中のスクリプトのファイルがあるかを確かめる。"""
    raise NotImplementedError
