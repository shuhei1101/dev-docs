from __future__ import annotations

import contextlib
import os
import re
import signal
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

HOOKS_DIR = Path(__file__).parents[3] / "plugins" / "dev-docs" / "hooks"
EVENT = {"session_id": "s1", "cwd": "/repo/sample", "source": "clear"}


def _clone_with_recorder(tmp_path: Path) -> tuple[Path, Path, Path]:
    """起動の引数と PID を記録して待ち続ける偽の Python を持つクローンを作る。"""
    clone = tmp_path / "clone"
    python = clone / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    args_file = tmp_path / "args.txt"
    pid_file = tmp_path / "pid.txt"
    python.write_text(
        f'#!/bin/sh\necho "$@" > "{args_file}"\necho $$ > "{pid_file}"\nexec sleep 30\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    return clone, args_file, pid_file


def _hooks_with_context_timeout(tmp_path: Path, seconds: int) -> Path:
    """`CONTEXT_TIMEOUT_SEC` を `seconds` に差し替えたセッション開始のフックのコピーを置き、そのフォルダを返す。"""
    source = HOOKS_DIR / "session_start.py"
    text = source.read_text(encoding="utf-8")
    replaced = re.sub(
        r"^CONTEXT_TIMEOUT_SEC = \d+$", f"CONTEXT_TIMEOUT_SEC = {seconds}", text, flags=re.M
    )
    assert replaced != text
    folder = tmp_path / "hooks"
    folder.mkdir()
    (folder / "session_start.py").write_text(replaced, encoding="utf-8")
    return folder


def _wait_for(path: Path, timeout_sec: float = 5) -> str:
    """ファイルができるまで待ち、中身を返す。"""
    deadline = time.monotonic() + timeout_sec
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    return path.read_text(encoding="utf-8").strip()


def test_normal_when_server_listening(
    tmp_path: Path, run_hook: Callable[..., Any], context_server: Callable[..., Any]
) -> None:
    """つながったサーバーの `POST /_admin/session-context` の文を文脈に入れる（正常系）。"""
    # 準備・実行
    with context_server("ctx 文") as server:
        result = run_hook(
            "session_start",
            EVENT,
            {
                "DEV_DOCS_PORT": str(server.port),
                "DEV_DOCS_CONFIG": str(tmp_path / "missing.yaml"),
            },
        )
    # 検証
    context = result.output["hookSpecificOutput"]["additionalContext"]
    assert result.code == 0
    assert context == "ctx 文"
    assert server.bodies == [{"cwd": "/repo/sample", "session_id": "s1", "reason": "clear"}]


def test_normal_when_server_down(
    tmp_path: Path, run_hook: Callable[..., Any], free_port: Callable[[], int]
) -> None:
    """つながらなければ `dev-docs serve` を切り離して起動し、つなぎ直しを案内する（正常系）。"""
    # 準備
    clone, args_file, pid_file = _clone_with_recorder(tmp_path)
    settings = tmp_path / "settings.yaml"
    settings.write_text(f'version: "1"\nclone: {clone}\n', encoding="utf-8")
    started = time.monotonic()
    # 実行
    result = run_hook(
        "session_start",
        EVENT,
        {"DEV_DOCS_PORT": str(free_port()), "DEV_DOCS_CONFIG": str(settings)},
    )
    elapsed = time.monotonic() - started
    # 検証
    try:
        recorded = _wait_for(args_file)
        context = result.output["hookSpecificOutput"]["additionalContext"]
        assert result.code == 0
        assert recorded == "-m dev_docs serve"
        assert "/mcp" in context
        assert "つなぎ直して" in context
        # 起動したプロセスは 30 秒動き続けるので、待たずに戻っている
        assert elapsed < 10
    finally:
        with contextlib.suppress(OSError, ValueError):
            os.kill(int(_wait_for(pid_file, 1)), signal.SIGTERM)


def test_normal_when_terminal_config_missing(
    tmp_path: Path, run_hook: Callable[..., Any], free_port: Callable[[], int]
) -> None:
    """端末の設定が無ければ、理由と global-setup の案内を入れる（正常系）。"""
    # 準備
    config = tmp_path / "missing.yaml"
    # 実行
    result = run_hook(
        "session_start",
        EVENT,
        {"DEV_DOCS_PORT": str(free_port()), "DEV_DOCS_CONFIG": str(config)},
    )
    # 検証
    context = result.output["hookSpecificOutput"]["additionalContext"]
    assert result.code == 0
    assert str(config) in context
    assert "/dev-docs:global-setup" in context


def test_normal_when_context_timeout(
    tmp_path: Path, run_hook: Callable[..., Any], context_server: Callable[..., Any]
) -> None:
    """`POST /_admin/session-context` が `CONTEXT_TIMEOUT_SEC` 秒で返らなければ、打ち切った秒数を入れて戻る（正常系）。"""
    # 準備
    hooks_dir = _hooks_with_context_timeout(tmp_path, 2)
    started = time.monotonic()
    # 実行
    with context_server("ctx", hold_sec=4) as server:
        result = run_hook(
            "session_start",
            EVENT,
            {
                "DEV_DOCS_PORT": str(server.port),
                "DEV_DOCS_CONFIG": str(tmp_path / "missing.yaml"),
            },
            hooks_dir=hooks_dir,
        )
    elapsed = time.monotonic() - started
    # 検証
    context = result.output["hookSpecificOutput"]["additionalContext"]
    assert result.code == 0
    assert elapsed < 3
    assert "取れませんでした" in context
    assert "2 秒で打ち切りました" in context
    assert "status" in context
    assert "起動しました" not in context
