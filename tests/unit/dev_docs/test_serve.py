from __future__ import annotations

import argparse
import socket
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.features.sources.types import SourceStatus
from dev_docs.main import PortInUseError, build_handlers, check_port, reload_sources, run_serve


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


@pytest.fixture
def serve_settings(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    sample_files: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """配信できる配信元 1 つの端末の設定を `DEV_DOCS_CONFIG` に入れ、その場所を返す。"""
    write_files(tmp_path / "ws", sample_files)
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        f'version: "1"\nclone: {tmp_path}\nstate_dir: {tmp_path / "state"}\n'
        f"sources:\n  - config: {tmp_path / 'ws' / 'dev-docs.yaml'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(settings))
    return settings


def test_run_serve(
    serve_settings: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """待ち受けて配信元を出す（正常系）。"""
    # 準備
    port = _free_port()
    monkeypatch.setenv("DEV_DOCS_PORT", str(port))
    configs: list[dict[str, Any]] = []
    real_config = uvicorn.Config

    def recording_config(*args: Any, **kwargs: Any) -> uvicorn.Config:
        configs.append(kwargs)
        return real_config(*args, **kwargs)

    def fake_run(self: uvicorn.Server, *args: Any, **kwargs: Any) -> None:
        self.started = True

    monkeypatch.setattr(uvicorn, "Config", recording_config)
    monkeypatch.setattr(uvicorn.Server, "run", fake_run)
    # 実行
    code = run_serve(argparse.Namespace())
    # 検証
    output = capsys.readouterr().out
    assert code == 0
    assert f"http://127.0.0.1:{port}/" in output
    assert "sample" in output
    assert configs[0]["host"] == "127.0.0.1"


def test_run_serve_when_config_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """端末の設定が違反する（異常系）。"""
    # 準備
    settings = tmp_path / "settings.yaml"
    settings.write_text(
        'version: "1"\nclone: /tmp/clone\nport: abc\nsources:\n  - id: a\n', encoding="utf-8"
    )
    monkeypatch.setenv("DEV_DOCS_CONFIG", str(settings))
    # 実行
    code = run_serve(argparse.Namespace())
    # 検証
    error = capsys.readouterr().err
    assert code == 2
    assert "sources[0].config" in error
    assert "port" in error


def test_run_serve_when_port_in_use(
    serve_settings: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ポートが使用中（異常系）。"""
    # 準備・実行
    with _listening() as port:
        monkeypatch.setenv("DEV_DOCS_PORT", str(port))
        code = run_serve(argparse.Namespace())
    # 検証
    error = capsys.readouterr().err
    assert code == 3
    assert str(port) in error
    assert "DEV_DOCS_PORT" in error


def test_check_port() -> None:
    """空いているポート（正常系）。"""
    # 準備
    port = _free_port()
    # 実行・検証
    check_port("127.0.0.1", port)


def test_check_port_when_in_use() -> None:
    """使用中のポート（異常系）。"""
    # 準備・実行・検証
    with _listening() as port, pytest.raises(PortInUseError) as exc_info:
        check_port("127.0.0.1", port)
    assert exc_info.value.port == port


def test_build_handlers(
    tmp_path: Path,
    write_files: Callable[[Path, dict[str, str]], None],
    sample_files: dict[str, str],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """部品を作り配信元を読む（正常系）。"""
    # 準備
    write_files(tmp_path / "ok", sample_files)
    write_files(
        tmp_path / "broken",
        {"dev-docs.yaml": "name: broken\ndocuments:\n  - id: rules\n    type: yaml\n"},
    )
    state_dir = tmp_path / "new-state"
    terminal = make_terminal_config(
        state_dir=state_dir,
        sources=[
            make_entry(str(tmp_path / "ok" / "dev-docs.yaml")),
            make_entry(str(tmp_path / "broken" / "dev-docs.yaml")),
        ],
    )
    # 実行
    handlers = build_handlers(terminal)
    # 検証
    assert state_dir.is_dir()
    assert len(handlers.registry.served()) == 1
    assert len(handlers.registry.statuses()) == 2


class _Recorder:
    """呼ばれた順を共有の記録へ残す部品の偽物。"""

    def __init__(
        self, name: str, calls: list[str], statuses: list[SourceStatus] | None = None
    ) -> None:
        self._name = name
        self._calls = calls
        self._statuses = statuses or []

    def reload(self, terminal: TerminalConfig) -> list[SourceStatus]:
        self._calls.append(f"{self._name}.reload")
        return self._statuses

    def clear(self) -> None:
        self._calls.append(f"{self._name}.clear")


def test_reload_sources(
    make_terminal_config: Callable[..., TerminalConfig],
    make_status: Callable[..., SourceStatus],
) -> None:
    """読み直してから控えを捨てる（正常系）。"""
    # 準備
    calls: list[str] = []
    statuses = [make_status("sample", 0)]
    registry = _Recorder("registry", calls, statuses)
    # 実行
    result = reload_sources(
        make_terminal_config(),
        registry=registry,  # type: ignore[arg-type]
        store=_Recorder("store", calls),
        checker=_Recorder("checker", calls),
        converter=_Recorder("converter", calls),
    )
    # 検証
    assert calls[0] == "registry.reload"
    assert sorted(calls[1:]) == ["checker.clear", "converter.clear", "store.clear"]
    assert result == statuses
