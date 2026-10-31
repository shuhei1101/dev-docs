"""説明の要求と結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dev_docs.features.access.types import SourceAccess, Workplace
from dev_docs.features.history.types import WorktreeInfo


class DescribeRequest(BaseModel):
    """`describe` の引数。"""

    model_config = ConfigDict(extra="forbid")

    source: str | None = None
    kind: str | None = None
    worktree: str | None = None
    format: Literal["markdown", "json"] = "markdown"
    cwd: str | None = None
    outside_scope: bool = Field(
        default=False,
        description=(
            "true のとき、scope に当たらない配信元を outside_read が真なら"
            "作業範囲の外（参考）として読む（source が ID 1 つのときだけ効く）。引数なしの一覧には効かない"
        ),
    )


@dataclass(frozen=True)
class KindSummary:
    """種類の一覧の 1 行。"""

    id: str
    description: str


@dataclass(frozen=True)
class SourceListResult:
    """引数なしの結果。"""

    workplace: Workplace
    sources: list[SourceAccess]


@dataclass(frozen=True)
class SourceGuideResult:
    """`source` だけの結果。"""

    source_id: str
    instructions: str
    kinds: list[KindSummary]
    outside_scope: bool = False
    refs: dict[str, list[str]] | None = None
    worktrees: list[WorktreeInfo] | None = None


@dataclass(frozen=True)
class KindSchemaResult:
    """`source`・`kind` の結果。"""

    source_id: str
    kind: str
    schema_text: str
    schema: dict[str, Any]
    metadata: dict[str, str] = field(default_factory=dict)
    outside_scope: bool = False
