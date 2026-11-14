"""SessionStart のフック。落ちている dev-docs を起動する。

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
    # 落ちているサーバーは、端末の設定のクローンで起動する
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
