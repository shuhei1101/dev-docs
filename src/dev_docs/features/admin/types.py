"""管理の MCP の `status` の要求と結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 設定の `version` と dev-docs が読み込めるバージョンの比較
type VersionState = Literal["current", "old", "newer"]


@dataclass(frozen=True)
class SourceState:
    """`status` が返却する配信元 1 つの状態（project-index の状態のコピー）。"""

    id: str | None
    status: Literal["serving", "not_served", "disabled", "pending_reload"]
    errors: list[str]


@dataclass(frozen=True)
class TerminalState:
    """読み込んだ端末の設定のパスとバージョンの新旧。"""

    file: str
    version_state: VersionState


@dataclass(frozen=True)
class ProjectIndexState:
    """`status` の `project_index`。"""

    address: str
    reachable: bool
    error: str | None


@dataclass(frozen=True)
class ServerStatus:
    """`status` の結果。"""

    address: str
    version: str
    pid: int
    terminal: TerminalState
    project_index: ProjectIndexState
    sources: list[SourceState]
    leftover_sources: list[str] = field(default_factory=list)


class FormatRequest(BaseModel):
    """`status` の引数。"""

    model_config = ConfigDict(extra="forbid")

    format: Literal["markdown", "json"] = Field(default="markdown", description="返却する形式")
