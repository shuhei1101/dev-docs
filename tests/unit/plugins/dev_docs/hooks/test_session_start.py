from __future__ import annotations

import io
import json
import socket
import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _free_port() -> int:
    """OS が払い出して閉じたポートの番号を返す。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _listening() -> Iterator[int]:
    """テストが `listen` しているポートの番号を渡す。"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield int(sock.getsockname()[1])


def _stdin(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """標準入力を、渡した文字列に差し替える。"""
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_main_when_listening(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """つながれば文脈を入れる（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    fetched: list[tuple[int, dict[str, str]]] = []

    def fake_fetch(port: int, payload: dict[str, str]) -> str:
        fetched.append((port, payload))
        return "ctx"

    monkeypatch.setattr(hook, "is_listening", lambda port: True)
    monkeypatch.setattr(hook, "fetch_context", fake_fetch)
    monkeypatch.setenv("DEV_DOCS_PORT", "8799")
    _stdin(
        monkeypatch,
        json.dumps({"session_id": "s1", "cwd": "/repo", "source": "clear"}),
    )
    # 実行
    code = hook.main()
    # 検証
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert output["hookSpecificOutput"]["additionalContext"] == "ctx"
    assert fetched[0][0] == 8799
    assert fetched[0][1]["reason"] == "clear"
    assert fetched[0][1]["cwd"] == "/repo"
    assert fetched[0][1]["session_id"] == "s1"


def test_main_when_down(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """つながらなければ起動して案内する（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    clone = tmp_path / "clone"
    (clone / ".venv" / "bin").mkdir(parents=True)
    (clone / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    config = tmp_path / "settings.yaml"
    config.write_text(f'version: "1"\nclone: {clone}\n', encoding="utf-8")
    started: list[Path] = []
    monkeypatch.setattr(hook, "is_listening", lambda port: False)
    monkeypatch.setattr(hook, "start_server", started.append)
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(config))
    _stdin(
        monkeypatch,
        json.dumps({"session_id": "s1", "cwd": "/repo", "source": "startup"}),
    )
    # 実行
    code = hook.main()
    # 検証
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert started == [clone]
    assert output["hookSpecificOutput"]["additionalContext"] == hook.RECONNECT_GUIDE


def test_main_when_config_missing(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """端末の設定が無ければ global-setup を案内する（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    config = tmp_path / "missing.yaml"
    started: list[Path] = []
    monkeypatch.setattr(hook, "is_listening", lambda port: False)
    monkeypatch.setattr(hook, "start_server", started.append)
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(config))
    _stdin(
        monkeypatch,
        json.dumps({"session_id": "s1", "cwd": "/repo", "source": "startup"}),
    )
    # 実行
    code = hook.main()
    # 検証
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert code == 0
    assert str(config) in context
    assert "/dev-docs:global-setup" in context
    assert started == []


def test_main_when_context_failed(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """文脈を取れなければ status を案内する（異常系）。"""
    # 準備
    hook = load_hook("session_start")

    def failing_fetch(port: int, payload: dict[str, str]) -> str:
        raise TimeoutError("timed out")

    monkeypatch.setattr(hook, "is_listening", lambda port: True)
    monkeypatch.setattr(hook, "fetch_context", failing_fetch)
    _stdin(
        monkeypatch,
        json.dumps({"session_id": "s1", "cwd": "/repo", "source": "startup"}),
    )
    # 実行
    code = hook.main()
    # 検証
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert code == 0
    assert "status" in context


def test_main_when_input_unparsable(
    load_hook: Callable[[str], ModuleType],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """読めない入力では何も出さない（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    _stdin(monkeypatch, "{")
    # 実行
    code = hook.main()
    # 検証
    assert code == 0
    assert capsys.readouterr().out == ""


def test_is_listening(load_hook: Callable[[str], ModuleType]) -> None:
    """待ち受けているポート（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    # 実行・検証
    with _listening() as port:
        assert hook.is_listening(port) is True


def test_is_listening_when_closed(load_hook: Callable[[str], ModuleType]) -> None:
    """待ち受けていないポート（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    port = _free_port()
    # 実行
    result = hook.is_listening(port)
    # 検証
    assert result is False


def test_read_clone(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """引用符と ~ を扱う（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    config = tmp_path / "settings.yaml"
    config.write_text(
        'version: "1"\nclone: "~/dev-docs"  # クローン\nsources:\n  - id: a\n    clone: /other\n',
        encoding="utf-8",
    )
    # 実行
    result = hook.read_clone(config)
    # 検証
    assert result == Path.home() / "dev-docs"


def test_read_clone_when_missing(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """行かファイルが無い（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    no_line = tmp_path / "no_line.yaml"
    no_line.write_text('version: "1"\n', encoding="utf-8")
    # 実行
    result_no_line = hook.read_clone(no_line)
    result_no_file = hook.read_clone(tmp_path / "missing.yaml")
    # 検証
    assert result_no_line is None
    assert result_no_file is None


@pytest.mark.filterwarnings("ignore:subprocess .* is still running:ResourceWarning")
def test_start_server(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """切り離して起動する（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    clone = tmp_path / "clone"
    python = clone / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    record = tmp_path / "args.txt"
    python.write_text(f'#!/bin/sh\necho "$@" > "{record}"\n', encoding="utf-8")
    python.chmod(0o755)
    # 実行
    hook.start_server(clone)
    # 検証
    deadline = time.monotonic() + 5
    while not record.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert record.read_text(encoding="utf-8").strip() == "-m dev_docs serve"


def test_start_server_when_no_venv(load_hook: Callable[[str], ModuleType], tmp_path: Path) -> None:
    """.venv が無い（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    # 実行・検証
    with pytest.raises(FileNotFoundError):
        hook.start_server(tmp_path)


def test_fetch_context(
    load_hook: Callable[[str], ModuleType],
    context_server: Callable[..., Any],
) -> None:
    """context を返す（正常系）。"""
    # 準備
    hook = load_hook("session_start")
    payload = {"cwd": "/repo", "session_id": "s1", "reason": "startup"}
    # 実行
    with context_server({"context": "ctx"}) as server:
        result = hook.fetch_context(server.port, payload)
    # 検証
    assert result == "ctx"
    assert server.bodies == [payload]


def test_fetch_context_when_timeout(
    load_hook: Callable[[str], ModuleType],
    context_server: Callable[..., Any],
) -> None:
    """3 秒で打ち切る（異常系）。"""
    # 準備
    hook = load_hook("session_start")
    payload: dict[str, Any] = {"cwd": "/repo", "reason": "startup"}
    started = time.monotonic()
    # 実行
    with context_server({"context": "ctx"}, hold_sec=5) as server, pytest.raises(TimeoutError):
        hook.fetch_context(server.port, payload)
    # 検証
    assert time.monotonic() - started < 4
