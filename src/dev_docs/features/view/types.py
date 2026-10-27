"""画面の型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict


@dataclass(frozen=True)
class ScreenPath:
    """`/{source}[@{ref}]/{path}` を分けたもの。"""

    source_id: str
    ref: str | None
    page: str


@dataclass(frozen=True)
class NavLink:
    """サイドバーの 1 行。"""

    title: str
    page: str


@dataclass(frozen=True)
class NavGroup:
    """見出しと、その下の行・入れ子の見出し。"""

    title: str | None
    links: list[NavLink] = field(default_factory=list)
    groups: list[NavGroup] = field(default_factory=list)


@dataclass(frozen=True)
class NavTab:
    """上のタブ 1 つとそのサイドバー。"""

    title: str
    sidebar: NavGroup


@dataclass(frozen=True)
class PageState:
    """画面のスクリプトへ JSON で埋め込む値。"""

    source_id: str | None = None
    sources: list[dict[str, str]] = field(default_factory=list)
    git: bool = False
    ref: str | None = None
    ref_in_url: str | None = None
    default_ref: str | None = None
    doc_page: str | None = None
    diff: dict[str, str] | None = None
    github_repository: str | None = None
    issue_labels: list[str] = field(default_factory=list)
    table_keys: list[str] = field(default_factory=list)
    hidden_columns: dict[str, list[str]] = field(default_factory=dict)


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
