from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from dev_docs.features.describe.source_checks import SourceChecks
from dev_docs.features.settings.types import SourceEntry, TerminalConfig
from dev_docs.features.sources.types import ServedSource
from dev_docs.main import Handlers, build_handlers


def _sample(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> tuple[Handlers, ServedSource]:
    """管理用の YAML に無いファイルが 1 件ある配信元 sample を読んだ部品と、その配信元を返す。"""
    terminal = make_terminal_config(
        sources=[make_entry(str(make_source_dir("sample", unindexed=1)), source_id="sample")]
    )
    handlers = build_handlers(terminal)
    handlers.reload_sources(terminal)
    return handlers, handlers.registry.get("sample")


def test_source_checks_refresh(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """検査して結果を持つ（正常系）。"""
    # 準備
    handlers, source = _sample(make_source_dir, make_terminal_config, make_entry)
    checks = SourceChecks()
    # 実行
    result = checks.refresh(handlers.store, source)
    # 検証
    held = checks.get("sample")
    assert len(result.report.unindexed_files) == 1
    assert held is not None
    assert len(held.report.unindexed_files) == 1


def test_source_checks_get_when_unchecked() -> None:
    """検査していない配信元（正常系）。"""
    # 準備
    checks = SourceChecks()
    # 実行
    result = checks.get("sample")
    # 検証
    assert result is None


def test_source_checks_refresh_later(
    make_source_dir: Callable[..., Path],
    make_terminal_config: Callable[..., TerminalConfig],
    make_entry: Callable[..., SourceEntry],
) -> None:
    """裏で検査し直す（正常系）。"""
    # 準備
    handlers, source = _sample(make_source_dir, make_terminal_config, make_entry)
    checks = SourceChecks()
    # 実行
    thread = checks.refresh_later(handlers.store, [source])
    thread.join(timeout=30)
    # 検証
    assert checks.get("sample") is not None
