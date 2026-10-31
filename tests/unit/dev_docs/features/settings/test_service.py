from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from dev_docs.features.settings.service import save_sources
from dev_docs.features.settings.types import SourceEntry, TerminalConfig, TerminalConfigInvalidError
from dev_docs.features.sources.types import SourceStatus

SETTINGS_TEXT = (
    'version: "1"\n'
    "clone: /tmp/clone\n"
    "port: 8781  # ポート\n"
    "sources:\n"
    "  - config: /tmp/a/dev-docs.yaml\n"
)


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    """端末の設定のファイルを書いてパスを返す。"""
    path = tmp_path / "settings.yaml"
    path.write_text(SETTINGS_TEXT, encoding="utf-8")
    return path


@pytest.fixture
def fake_reload(
    make_status: Callable[..., SourceStatus],
) -> tuple[Callable[[TerminalConfig], list[SourceStatus]], list[TerminalConfig]]:
    """`serving` を 2 つ返し、呼ばれた端末の設定を記録する配信元の読み直しの偽物。"""
    calls: list[TerminalConfig] = []

    def _reload(terminal: TerminalConfig) -> list[SourceStatus]:
        calls.append(terminal)
        return [make_status("a", 0), make_status("b", 1)]

    return _reload, calls


def test_save_sources(
    settings_path: Path,
    fake_reload: tuple[Callable[[TerminalConfig], list[SourceStatus]], list[TerminalConfig]],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """sources だけを書き換えコメントを保つ（正常系）。"""
    # 準備
    reload, calls = fake_reload
    sources = [
        make_entry("/tmp/a/dev-docs.yaml", source_id="a"),
        make_entry("/tmp/b/dev-docs.yaml", source_id="b"),
    ]
    # 実行
    result = save_sources(sources, path=settings_path, reload=reload, lock=threading.Lock())
    # 検証
    text = settings_path.read_text(encoding="utf-8")
    assert text.count("config:") == 2
    assert "port: 8781  # ポート" in text
    assert len(calls) == 1
    assert len(calls[0].sources) == 2
    assert [status.id for status in result] == ["a", "b"]


def test_save_sources_when_defaults(
    settings_path: Path,
    fake_reload: tuple[Callable[[TerminalConfig], list[SourceStatus]], list[TerminalConfig]],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """既定値のキーを書かない（正常系）。"""
    # 準備
    reload, _ = fake_reload
    sources = [make_entry("/tmp/a/dev-docs.yaml", source_id="a", enabled=True)]
    # 実行
    save_sources(sources, path=settings_path, reload=reload, lock=threading.Lock())
    # 検証
    text = settings_path.read_text(encoding="utf-8")
    assert "enabled" not in text
    assert "scope" not in text


def test_save_sources_when_outside_read_false(
    settings_path: Path,
    fake_reload: tuple[Callable[[TerminalConfig], list[SourceStatus]], list[TerminalConfig]],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """既定値と違う outside_read を書く（正常系）。"""
    # 準備
    reload, _ = fake_reload
    sources = [make_entry("/tmp/a/dev-docs.yaml", source_id="a", outside_read=False)]
    # 実行
    save_sources(sources, path=settings_path, reload=reload, lock=threading.Lock())
    # 検証
    text = settings_path.read_text(encoding="utf-8")
    assert "outside_read: false" in text


def test_save_sources_when_invalid(
    settings_path: Path,
    fake_reload: tuple[Callable[[TerminalConfig], list[SourceStatus]], list[TerminalConfig]],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """検証に通らない（異常系）。"""
    # 準備
    reload, calls = fake_reload
    sources = [
        make_entry("/tmp/a/dev-docs.yaml", source_id="a"),
        make_entry("/tmp/b/dev-docs.yaml", source_id="a"),
    ]
    # 実行・検証
    with pytest.raises(TerminalConfigInvalidError):
        save_sources(sources, path=settings_path, reload=reload, lock=threading.Lock())
    assert settings_path.read_text(encoding="utf-8") == SETTINGS_TEXT
    assert calls == []
