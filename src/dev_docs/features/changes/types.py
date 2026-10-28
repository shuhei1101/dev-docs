"""変更の一覧の要求と結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dev_docs.features.search.types import LIMIT_DEFAULT, MAX_CHARS_DEFAULT, Condition, Group

LAST_READ_LABEL = "前回読んだ時点"
WORKTREE_LABEL = "作業ツリー"


class ChangesRequest(BaseModel):
    """`list_changes` の引数。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: str | list[str] | None = None
    worktree: str | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    filter: Condition | Group | None = None
    view: Literal["summary", "full"] = "summary"
    limit: int = LIMIT_DEFAULT
    cursor: str | None = None
    max_chars: int = MAX_CHARS_DEFAULT
    format: Literal["markdown", "json"] = "markdown"
    cwd: str | None = None
    session_id: str | None = None
    agent_id: str | None = None


@dataclass(frozen=True)
class RangePoint:
    """区間の始点か終点。"""

    input: str
    commit: str | None = None
    date: datetime | None = None


@dataclass(frozen=True)
class ChangeItem:
    """変わった文書 1 件。"""

    id: str
    source: str | None
    change: Literal["added", "modified", "deleted"]
    keys: list[str]
    values: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    diff: str | None = None
    # 変わった文書の今の場所と返した範囲。`to` を渡した呼び出しと `deleted` では `None`
    path: str | None = None
    scope: Literal["section", "summary"] | None = None


@dataclass(frozen=True)
class ChangesResult:
    """`list_changes` が返すもの。"""

    range_from: RangePoint
    range_to: RangePoint
    total_count: int
    items: list[ChangeItem] = field(default_factory=list)
    next_cursor: str | None = None
    truncated: bool = False
    notes: list[str] = field(default_factory=list)
