"""SessionStart のフック。落ちている dev-docs を、systemd --user の unit か切り離したプロセスで起動する。

Usage:
# Claude Code が stdin に SessionStart の入力の JSON を指定して実行する
python3 session_start.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DEFAULT_PORT = 8781
# `XDG_CONFIG_HOME` が無いか空の文字列か相対パスのときの設定の配置先の親
DEFAULT_CONFIG_HOME = "~/.config"
CONFIG_FILE = "dev-docs/settings.yaml"
# ポートへの TCP 接続を打ち切る秒数
CONNECT_TIMEOUT_SEC = 0.5
# 起動したときに文脈に入れる文
RECONNECT_GUIDE = (
    "dev-docs を起動しました。"
    "このセッションで dev-docs の管理の MCP を使用するには /mcp で dev-docs に再接続してください。"
)
CLONE_KEY = "clone:"
# 起動に使用する systemd --user の unit の名前を持つ環境変数（空の文字列は unit を使用しない）
UNIT_ENV = "DEV_DOCS_UNIT"
DEFAULT_UNIT = "dev-docs.service"
# `systemctl --user` の呼び出しを打ち切る秒数（実測の最大 0.04 秒に 50% を乗せて切り上げた値）
SYSTEMCTL_TIMEOUT_SEC = 0.1


class UnitStartError(Exception):
    """unit があるか分からないか、unit の起動に失敗したことを表す。本文が理由。"""


def is_listening(port: int) -> bool:
    """`127.0.0.1:{port}` に TCP でつながるかを返却する。"""
    try:
        socket.create_connection(("127.0.0.1", port), timeout=CONNECT_TIMEOUT_SEC).close()
    except OSError:
        return False
    return True


def config_path(env: Mapping[str, str]) -> Path:
    """サーバーと同じ規則で端末の設定のパスを決める。"""
    value = env.get("DEV_DOCS_CONFIG")
    if value:
        return Path(value).expanduser()
    home = env.get("XDG_CONFIG_HOME") or ""
    base = Path(home) if os.path.isabs(home) else Path(DEFAULT_CONFIG_HOME).expanduser()
    return base / CONFIG_FILE


def read_clone(config: Path) -> Path | None:
    """端末の設定のトップレベルの `clone:` の行だけを読み込む（標準ライブラリに YAML が無いため）。"""
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        # 行頭が `clone:` の最初の行だけを参照する（字下げした行は別のキー）
        if line.startswith(CLONE_KEY):
            value = line[len(CLONE_KEY) :].split("#", 1)[0].strip().strip("\"'")
            return Path(value).expanduser() if value else None
    return None


def start_server(clone: Path) -> None:
    """クローンの `.venv` で `dev-docs serve` を切り離して起動し、待たずに戻る。"""
    python = clone / ".venv" / "bin" / "python"
    if not python.exists():
        raise FileNotFoundError(str(python))
    subprocess.Popen(
        [str(python), "-m", "dev_docs", "serve"],
        cwd=clone,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def unit_name(env: Mapping[str, str]) -> str | None:
    """起動に使用する unit の名前を決める（unit を使用しないときは `None`）。"""
    value = env.get(UNIT_ENV)
    # 環境変数が無ければ既定の unit
    if value is None:
        return DEFAULT_UNIT
    # 空の文字列は unit を使用しない
    return value.strip() or None


def unit_exists(unit: str) -> bool:
    """`systemctl --user cat {unit}` で unit があるかを返却する。"""
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "cat", unit],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SYSTEMCTL_TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError:
        # systemctl が無い端末は unit が無い扱い
        return False
    except subprocess.TimeoutExpired as error:
        # 遅いだけで unit はありうるので、unit が無い扱いにはしない
        raise UnitStartError(
            f"systemctl --user cat が {SYSTEMCTL_TIMEOUT_SEC} 秒で終わらなかった"
        ) from error
    return completed.returncode == 0


def start_unit(unit: str) -> None:
    """`systemctl --user start --no-block {unit}` で unit の起動を依頼し、待たずに戻る。"""
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "start", "--no-block", unit],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SYSTEMCTL_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise UnitStartError(
            f"systemctl --user start が {SYSTEMCTL_TIMEOUT_SEC} 秒で終わらなかった"
        ) from error
    except OSError as error:
        raise UnitStartError(str(error)) from error
    if completed.returncode != 0:
        # systemctl の標準エラーを理由にする（空なら終了コード）
        reason = completed.stderr.strip() or f"終了コード {completed.returncode}"
        raise UnitStartError(reason)


def _unit_unavailable(unit: str, reason: str) -> str:
    """unit を起動できないことと、状態の確認方法を通知する文を作る。"""
    return (
        f"dev-docs の unit {unit} を起動できませんでした（{reason}）。"
        f"systemctl --user status {unit} で状態を確認してください。"
    )


def _unavailable(reason: str) -> str:
    """起動できないことと、端末の設定の作り方を通知する文を作る。"""
    return (
        f"dev-docs を起動できませんでした（{reason}）。"
        "/dev-docs:global-setup で端末の設定を作ってください。"
    )


def _start_context(clone: Path | None, config: Path) -> str:
    """サーバーを起動し、起動できたときは案内、できなかったときは理由の文を返却する。"""
    # 端末の設定か clone の行が無い
    if clone is None:
        return _unavailable(str(config))
    # `{clone}/.venv/bin/python` が無い
    python = clone / ".venv" / "bin" / "python"
    if not python.exists():
        return _unavailable(str(python))
    try:
        start_server(clone)
    except OSError as error:
        return _unavailable(str(error))
    return RECONNECT_GUIDE


def _context(event: dict[str, Any]) -> str | None:
    """フックの入力から、セッションの文脈に入れる文を決める（入れないときは `None`）。"""
    port = int(os.environ.get("DEV_DOCS_PORT") or DEFAULT_PORT)
    # 待ち受けているサーバーには何も依頼しない
    if is_listening(port):
        return None
    # 落ちているサーバーは、unit があれば unit で起動する
    unit = unit_name(os.environ)
    if unit is not None:
        try:
            if unit_exists(unit):
                start_unit(unit)
                return RECONNECT_GUIDE
        except UnitStartError as error:
            # unit の外にプロセスを残さないため、切り離した起動へは切り替えない
            return _unit_unavailable(unit, str(error))
    # unit を使用しないか unit が無い端末は、端末の設定のクローンで切り離して起動する
    config = config_path(os.environ)
    return _start_context(read_clone(config), config)


def main() -> int:
    """stdin の JSON を読み込み、サーバーが落ちていれば起動して、入れる文だけを出す。"""
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(event, dict):
        return 0
    try:
        context = _context(event)
    except Exception as error:  # noqa: BLE001
        # どの失敗でもセッションを止めない
        context = f"dev-docs のフックが失敗しました（{error}）。"
    if context is None:
        return 0
    output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
