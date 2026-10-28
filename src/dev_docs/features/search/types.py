"""検索の要求と結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LIMIT_DEFAULT = 20
LIMIT_MAX = 100
MAX_CHARS_DEFAULT = 20000
MAX_CHARS_LIMIT = 40000
FIELD_CHARS_DEFAULT = 2000
FIELD_CHARS_FULL = 10000
SUMMARY_FIELDS = ("kind", "name", "description", "@chars", "version")


class Condition(BaseModel):
    """1 つの項目を比べる条件。"""

    model_config = ConfigDict(extra="forbid")

    field: str
    op: Literal[
        "eq",
        "ne",
        "prefix",
        "suffix",
        "contains",
        "not_contains",
        "regex",
        "gt",
        "gte",
        "lt",
        "lte",
        "exists",
        "not_exists",
    ]
    values: list[str] = Field(default_factory=list)
    match: Literal["any", "all"] = "any"
    case_sensitive: bool = False


class Group(BaseModel):
    """条件を AND か OR で束ねる。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    all_of: list[Condition | Group] | None = Field(default=None, alias="and")
    any_of: list[Condition | Group] | None = Field(default=None, alias="or")


class OrderKey(BaseModel):
    """並べ替えの 1 つのキー。"""

    model_config = ConfigDict(extra="forbid")

    field: str
    direction: Literal["asc", "desc"] = "asc"


class Snippets(BaseModel):
    """本文の代わりに一致した行の前後だけを返す指定。"""

    model_config = ConfigDict(extra="forbid")

    context_lines: int = 1
    max_per_doc: int = 3


class SearchRequest(BaseModel):
    """`search_docs` の引数。"""

    model_config = ConfigDict(extra="forbid")

    source: str | list[str] | None = None
    ref: str | None = None
    worktree: str | None = None
    filter: Condition | Group | None = None
    view: Literal["ids", "summary", "full", "count"] = "summary"
    fields: list[str] = Field(default_factory=list)
    exclude_fields: list[str] = Field(default_factory=list)
    order_by: list[OrderKey] = Field(default_factory=lambda: [OrderKey(field="id")])
    group_by: str | None = None
    limit: int = LIMIT_DEFAULT
    cursor: str | None = None
    skip: int = 0
    max_chars: int = MAX_CHARS_DEFAULT
    max_chars_per_field: int | None = None
    snippets: Snippets | None = None
    repeat_seen: bool = False
    format: Literal["markdown", "json"] = "markdown"
    cwd: str | None = None
    session_id: str | None = None
    agent_id: str | None = None


@dataclass(frozen=True)
class SearchItem:
    """返す 1 件の文書の項目。"""

    id: str
    source: str | None
    values: dict[str, Any]
    snippets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GroupCount:
    """`group_by` の値ごとの件数。"""

    value: str
    count: int


@dataclass(frozen=True)
class SearchResult:
    """`search_docs` が返すもの。"""

    total_count: int
    returned: int
    view: str
    per_source: dict[str, int] = field(default_factory=dict)
    next_cursor: str | None = None
    truncated: bool = False
    notes: list[str] = field(default_factory=list)
    groups: list[GroupCount] = field(default_factory=list)
    items: list[SearchItem] = field(default_factory=list)
    # Markdown の先頭に出す配信元の ID。JSON には出さない
    source_label: str = field(default="", metadata={"internal": True})
