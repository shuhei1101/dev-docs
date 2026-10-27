"""端末の設定の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from dev_docs.shared.errors import DevDocsError, Violation

if TYPE_CHECKING:
    from dev_docs.features.sources.types import SourceStatus


@dataclass
class SourceScope:
    """`sources[].scope` の `read`・`write`。"""

    read: list[str] = field(default_factory=list)
    write: list[str] | None = None


@dataclass
class SourceEntry:
    """端末の設定の `sources[]` の 1 行。"""

    config: list[str]
    id: str | None = None
    enabled: bool = True
    scope: SourceScope = field(default_factory=SourceScope)


@dataclass(frozen=True)
class TerminalConfig:
    """検証を通して既定値を埋めた端末の設定。"""

    file: Path
    version: str
    clone: Path
    state_dir: Path
    log_dir: Path
    port: int = 8781
    bind: str = "127.0.0.1"
    sources: list[SourceEntry] = field(default_factory=list)
    seen_retention_days: int = 7
    script_timeout_sec: int = 30


@dataclass
class SettingsSourcesRequest:
    """PUT `/_api/settings/sources` の本文。"""

    sources: list[SourceEntry]


@dataclass
class SettingsSourcesResponse:
    """読み直した後の配信元ごとの状態。"""

    sources: list[dict[str, object]]

    @classmethod
    def from_statuses(cls, statuses: list[SourceStatus]) -> SettingsSourcesResponse:
        """配信元の状態の並びから作る。"""
        raise NotImplementedError


@dataclass(kw_only=True)
class TerminalConfigInvalidError(DevDocsError):
    """端末の設定が無い・YAML として読めない・スキーマに違反すること。"""

    file: Path = Path()
    violations: list[Violation] = field(default_factory=list)
