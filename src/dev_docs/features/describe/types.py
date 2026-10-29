"""説明の要求と結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from dev_docs.features.access.types import SourceAccess, Workplace


class DescribeRequest(BaseModel):
    """`describe` の引数。"""

    model_config = ConfigDict(extra="forbid")

    source: str | None = None
    kind: str | None = None
    worktree: str | None = None
    format: Literal["markdown", "json"] = "markdown"
    cwd: str | None = None


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


@dataclass(frozen=True)
class KindSchemaResult:
    """`source`・`kind` の結果。"""

    source_id: str
    kind: str
    schema_text: str
    schema: dict[str, Any]
    metadata: dict[str, str] = field(default_factory=dict)
