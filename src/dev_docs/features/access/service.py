"""作業場所からの権限の判定と、読み書きする場所の解決。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dev_docs.features.access.types import AccessLevel, SourceAccess, Target, Workplace
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.types import ServedSource


def find_worktree(source: ServedSource, path: Path) -> Path | None:
    """パスが配信元のどのワークツリーの中かを返す。"""
    raise NotImplementedError


def access_of(source: ServedSource, cwd: Path | None) -> AccessLevel | None:
    """作業場所から配信元への権限を決める。"""
    raise NotImplementedError


def current_source(
    sources: Sequence[ServedSource], cwd: Path | None
) -> tuple[ServedSource, Path | None] | None:
    """作業場所を含む配信元のうち、直下が一番深いものを返す。"""
    raise NotImplementedError


def available_sources(cwd: str | None, *, registry: SourceRegistry) -> list[SourceAccess]:
    """作業場所から使える配信元と権限を並べる。"""
    raise NotImplementedError


def describe_workplace(cwd: str | None, *, registry: SourceRegistry) -> Workplace:
    """作業場所がどの配信元のクローン本体かワークツリーかを返す。"""
    raise NotImplementedError


def resolve_read_targets(
    *,
    registry: SourceRegistry,
    source: str | list[str] | None = None,
    ref: str | None = None,
    worktree: str | None = None,
    cwd: str | None = None,
) -> list[Target]:
    """MCP の `source`・`ref`・`worktree`・`cwd` から、読む配信元ごとの場所を解く。"""
    raise NotImplementedError


def resolve_write_target(
    *,
    registry: SourceRegistry,
    source: str | None = None,
    worktree: str | None = None,
    cwd: str | None = None,
) -> Target:
    """MCP の `source`・`worktree`・`cwd` から、書き込む場所を解く。"""
    raise NotImplementedError
