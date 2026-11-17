"""端末の設定の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dev_docs.integrations.project_index.client import PROJECT_INDEX_DEFAULT
from dev_docs.shared.api_model import ApiModel
from dev_docs.shared.errors import DevDocsError, Violation

if TYPE_CHECKING:
    from dev_docs.integrations.project_index.types import (
        SettingsSourcesView as ProjectIndexSettingsView,
    )
    from dev_docs.integrations.project_index.types import SourceState, SourceStateKind


class SourceScope(BaseModel):
    """`sources[].scope` の `read`・`write`。"""

    model_config = ConfigDict(extra="forbid")

    read: list[str] = Field(default_factory=list)
    write: list[str] | None = None


class SourceStorage(BaseModel):
    """`sources[].storage`（読み書きの方法）。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["git", "disk"]


type SettingsStatusKind = Literal["serving", "not_served", "disabled", "pending_reload"]


def settings_status(kind: SourceStateKind) -> SettingsStatusKind:
    """端末の設定の API の状態を画面の状態にする。`loading` は再読み込み待ちとして扱う。"""
    return "pending_reload" if kind == "loading" else kind


class SourceEntry(BaseModel):
    """設定画面が送信する `sources[]` の 1 行（project-index の端末の設定の行の構造）。"""

    model_config = ConfigDict(extra="forbid")

    config: list[str]
    id: str | None = None
    enabled: bool = True
    scope: SourceScope = SourceScope()
    outside_read: bool = True
    # `None` は送信しない（project-index がファイルの同じ配信元の行の今の値で埋める）
    storage: SourceStorage | None = None

    @field_validator("config", mode="before")
    @classmethod
    def _as_list(cls, value: Any) -> Any:
        """文字列 1 つで記載されたときも配列にする。"""
        return [value] if isinstance(value, str) else value


class TerminalConfig(BaseModel):
    """検証に合格して既定値を埋めた端末の設定。"""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    file: Path
    version: str
    clone: Path
    state_dir: Path
    log_dir: Path
    port: int = 8781
    bind: str = "127.0.0.1"
    project_index: str = PROJECT_INDEX_DEFAULT
    leftover_sources: list[str] = Field(default_factory=list)
    mdmark_version: str = "develop"


class SettingsSourcesRequest(ApiModel):
    """PUT `/_api/settings/sources` の本文。"""

    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry]
    # 画面が端末の設定の取得か前の保存で受けた内容のバージョン。`None` は照合しない
    expected_version: str | None = None


class SourceViolation(ApiModel):
    """検証で除外した理由 1 件。"""

    path: str
    reason: str


class SourceConfigVersion(ApiModel):
    """設定のバージョンとサーバーが読み込めるバージョン。"""

    config: str
    server: str


class SettingsSourceStatus(ApiModel):
    """再読み込みした後の配信元 1 つの状態。"""

    id: str | None
    status: SettingsStatusKind
    errors: list[SourceViolation] = Field(default_factory=list)
    config_version: SourceConfigVersion | None = None


class SettingsSourcesResponse(ApiModel):
    """再読み込みした後の配信元ごとの状態。"""

    sources: list[SettingsSourceStatus]
    # 保存した後の端末の設定の内容のバージョン
    version: str | None = None

    @classmethod
    def from_states(cls, states: list[SourceState]) -> SettingsSourcesResponse:
        """project-index の配信元の状態の並びから作る。"""
        items: list[SettingsSourceStatus] = []
        for status in states:
            item = SettingsSourceStatus(
                id=status.id,
                status=settings_status(status.status),
                errors=(
                    [SourceViolation(path=v.path, reason=v.rule) for v in status.errors]
                    if status.status == "not_served"
                    else []
                ),
            )
            if status.config_version is not None:
                config, server = status.config_version
                item.config_version = SourceConfigVersion(config=config, server=server)
            items.append(item)
        return cls(sources=items)

    @classmethod
    def from_view(cls, view: ProjectIndexSettingsView) -> SettingsSourcesResponse:
        """project-index の端末の設定の取得の結果の状態と内容のバージョンから作る。"""
        return cls(sources=cls.from_states(view.states).sources, version=view.version)


class SettingsSourceRow(ApiModel):
    """端末の設定の取得の `sources[]` の 1 行（行の値に配信元の状態を重ねたもの）。"""

    id: str | None
    config: list[str]
    enabled: bool
    scope: SourceScope
    status: SettingsStatusKind
    errors: list[SourceViolation] = Field(default_factory=list)
    config_version: SourceConfigVersion | None = None
    outside_read: bool = True
    storage: SourceStorage | None = None


class SettingsSourcesView(ApiModel):
    """GET `/_api/settings/sources` の応答。"""

    settings_path: str
    sources: list[SettingsSourceRow]
    # project-index の端末の設定の内容のバージョン（ファイル全体の内容のハッシュ）
    version: str | None = None


@dataclass(kw_only=True)
class TerminalConfigInvalidError(DevDocsError):
    """端末の設定が無い・YAML として読み込めない・スキーマに違反すること。"""

    status: ClassVar[int] = 422
    file: Path = Path()
    violations: list[Violation] = field(default_factory=list)
