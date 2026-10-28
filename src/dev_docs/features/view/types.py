"""画面の API の型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class NavItem(BaseModel):
    """サイドバーの見出しか文書の 1 行。"""

    kind: Literal["group", "page"]
    title: str
    path: str | None = None
    items: list[NavItem] = []


class NavTab(BaseModel):
    """上のタブ 1 つとそのサイドバー。"""

    title: str
    active: bool
    items: list[NavItem]


class ConversionError(BaseModel):
    """文書の取得の `conversion_error`（変換の失敗と同じフィールド）。"""

    reason: Literal["timeout", "exit", "not_runnable", "invalid_yaml"]
    kind: str
    script: str | None = None
    detail: str
    file: str | None = None
    line: int | None = None
    column: int | None = None


class GitHubTarget(BaseModel):
    """文書の取得の `github`（起票先）。"""

    repository: str
    issue_labels: list[str]


class DocumentResponse(BaseModel):
    """GET `/_api/sources/{source}/docs[/{path}]` の応答。"""

    source: str
    ref: str | None
    path: str
    markdown: str | None
    conversion_error: ConversionError | None
    tabs: list[NavTab]
    changed_items: list[str] | None
    github: GitHubTarget | None
    columns: dict[str, list[str]]
    table_keys: list[str]


class ScreenSearchItem(BaseModel):
    """画面の検索の結果の文書。"""

    path: str
    name: str
    snippets: list[str]


class ScreenSearchResult(BaseModel):
    """GET `/_api/sources/{source}/search` の応答。"""

    total_count: int
    items: list[ScreenSearchItem]


class ColumnsRequest(BaseModel):
    """PUT `/_api/sources/{source}/columns` の本文と応答。"""

    model_config = ConfigDict(extra="forbid")

    table: str
    hidden: list[str]
