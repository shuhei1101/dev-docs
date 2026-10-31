"""画面の API の型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from dev_docs.features.documents.types import AliasType
from dev_docs.shared.api_model import ApiModel


class NavItem(ApiModel):
    """サイドバーの見出しか文書の 1 行。"""

    kind: Literal["group", "page"]
    title: str
    path: str | None = None
    items: list[NavItem] = Field(default_factory=list)
    change: Literal["added", "modified", "deleted"] | None = None


class NavTab(ApiModel):
    """上のタブ 1 つとそのサイドバー。"""

    title: str
    active: bool
    items: list[NavItem]


class ConversionError(ApiModel):
    """文書の取得の `conversion_error`（変換の失敗と同じフィールド）。"""

    reason: Literal["timeout", "exit", "not_runnable", "invalid_yaml"]
    kind: str
    script: str | None = None
    detail: str
    file: str | None = None
    line: int | None = None
    column: int | None = None


class GitHubTarget(ApiModel):
    """文書の取得の `github`（起票先）。"""

    repository: str
    issue_labels: list[str]


class DocumentDiff(ApiModel):
    """文書の取得の `diff`（比べたリビジョンと、返した文書の変化・変わった項目）。"""

    base: str
    change: Literal["added", "modified"] | None
    changed_items: list[str] = Field(default_factory=list)


def _is_none(value: object) -> bool:
    """値を持たないか。"""
    return value is None


class AliasItem(ApiModel):
    """文書の取得の `aliases` の 1 件（`AliasEntry` の `extra` のキーは同じ階層に置く）。"""

    model_config = ConfigDict(
        alias_generator=ApiModel.model_config["alias_generator"],
        validate_by_name=True,
        serialize_by_alias=True,
        extra="allow",
    )

    id: str
    name: str
    aliases: list[str]
    # 値を持たないキーは載せない
    description: str | None = Field(default=None, exclude_if=_is_none)
    alias_type: AliasType
    avoid: list[str] | None = Field(default=None, exclude_if=_is_none)


class DocumentResponse(ApiModel):
    """GET `/_api/sources/{source}/docs[/{path}]` の応答。"""

    source: str
    ref: str | None
    path: str
    # 管理用の YAML の行の文書の本文のファイルのパス（拡張子つき）。画面が本文の相対リンクの基準にする
    body_path: str | None
    markdown: str | None
    conversion_error: ConversionError | None
    tabs: list[NavTab]
    github: GitHubTarget | None
    columns: dict[str, list[str]]
    table_keys: list[str]
    aliases: list[AliasItem] = Field(default_factory=list)
    diff: DocumentDiff | None
    updated_at: datetime


class ScreenSearchItem(ApiModel):
    """画面の検索の結果の文書。"""

    path: str
    name: str
    snippets: list[str]


class ScreenSearchResult(ApiModel):
    """GET `/_api/sources/{source}/search` の応答。"""

    total_count: int
    items: list[ScreenSearchItem]


class ColumnsRequest(ApiModel):
    """PUT `/_api/sources/{source}/columns` の本文と応答。"""

    model_config = ConfigDict(
        alias_generator=ApiModel.model_config["alias_generator"],
        validate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    table: str
    hidden: list[str]


class RefItem(ApiModel):
    """ブランチかタグ 1 つ。"""

    name: str
    commit: str


class CommitItem(ApiModel):
    """最近の commit 1 件。"""

    commit: str
    date: str
    subject: str


class RefsResponse(ApiModel):
    """GET `/_api/sources/{source}/refs` の応答。"""

    git: bool
    default_ref: str
    branches: list[RefItem] = Field(default_factory=list)
    tags: list[RefItem] = Field(default_factory=list)
    commits: list[CommitItem] = Field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class NavAutoCount:
    """`nav` の `auto` 1 つと、その条件に当たる文書の数。"""

    path: str
    tab: str
    filter: dict[str, Any] | None
    count: int
