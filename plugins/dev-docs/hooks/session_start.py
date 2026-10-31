"""SessionStart のフック。落ちている dev-docs を起動し、使える配信元と使い方を文脈に入れる。

Usage:
# Claude Code が stdin に SessionStart の入力の JSON を渡して実行する
python3 session_start.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_PORT = 8781
DEFAULT_CONFIG = "~/.config/dev-docs/settings.yaml"
# ポートへの TCP 接続を打ち切る秒数
CONNECT_TIMEOUT_SEC = 0.5
# `POST /_admin/session-context` を打ち切る秒数
CONTEXT_TIMEOUT_SEC = 11
# 起動したときに文脈に入れる文
RECONNECT_GUIDE = (
    "dev-docs を起動しました。"
    "このセッションで文書の MCP を使うには /mcp で dev-docs につなぎ直してください。"
)
CLONE_KEY = "clone:"


def is_listening(port: int) -> bool:
    """`127.0.0.1:{port}` に TCP でつながるかを返す。"""
    try:
        socket.create_connection(("127.0.0.1", port), timeout=CONNECT_TIMEOUT_SEC).close()
    except OSError:
        return False
    return True


def read_clone(config: Path) -> Path | None:
    """端末の設定のトップレベルの `clone:` の行だけを読む（標準ライブラリに YAML が無いため）。"""
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        # 行頭が `clone:` の最初の行だけを見る（字下げした行は別のキー）
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


def fetch_context(port: int, payload: dict[str, str]) -> str:
    """`POST /_admin/session-context` を 1 回呼び、応答の `context` を返す。"""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/_admin/session-context",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=CONTEXT_TIMEOUT_SEC) as response:
        body = json.load(response)
    context = body.get("context") if isinstance(body, dict) else None
    if not isinstance(context, str):
        raise ValueError("context がありません")
    return context


def _unavailable(reason: str) -> str:
    """起動できないことと、端末の設定の作り方を知らせる文を作る。"""
    return (
        f"dev-docs を起動できませんでした（{reason}）。"
        "/dev-docs:global-setup で端末の設定を作ってください。"
    )


def _start_context(clone: Path | None, config: Path) -> str:
    """サーバーを起動し、起動できたときは案内、できなかったときは理由の文を返す。"""
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


def _context(event: dict[str, Any]) -> str:
    """フックの入力から、セッションの文脈に入れる文を決める。"""
    port = int(os.environ.get("DEV_DOCS_PORT") or DEFAULT_PORT)
    payload = {"cwd": str(event.get("cwd", "")), "reason": str(event.get("source", "startup"))}
    # 会話キーは、あるものだけを送る
    for key in ("session_id", "agent_id"):
        if event.get(key):
            payload[key] = str(event[key])
    # 待ち受けているサーバーから文脈を取る
    if is_listening(port):
        try:
            return fetch_context(port, payload)
        except (OSError, ValueError) as error:
            # 打ち切ったとき: 理由の代わりに打ち切った秒数を入れる
            timed_out = isinstance(error, TimeoutError) or (
                isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError)
            )
            reason = f"{CONTEXT_TIMEOUT_SEC} 秒で打ち切りました" if timed_out else str(error)
            return (
                f"dev-docs の文脈を取れませんでした（{reason}）。"
                "管理の MCP の status で状態を確かめてください。"
            )
    # 落ちているサーバーは、端末の設定のクローンで起動する
    config = Path(os.environ.get("DEV_DOCS_CONFIG") or DEFAULT_CONFIG).expanduser()
    return _start_context(read_clone(config), config)


def main() -> int:
    """stdin の JSON を読み、文脈を取るかサーバーを起動して、`additionalContext` を出す。"""
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
    output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
