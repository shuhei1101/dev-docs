"""文書と読み込みの結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class Document:
    """ファイル 1 つか `records` の要素 1 つから作った 1 件の文書。"""

    id: str
    kind: str
    source_id: str
    path: str
    record_index: int | None
    data: dict[str, Any]
    body: str
    body_path: str | None
    metadata: dict[str, Any]
    version: str
    created: datetime | None
    updated: datetime | None


@dataclass(frozen=True)
class LoadProblem:
    """文書にできなかったファイルと理由。"""

    path: str
    reason: Literal["unreadable", "duplicate_id", "missing_body_file", "not_mapping"]
    detail: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class LoadResult:
    """読めた文書と読めなかったファイル。"""

    documents: list[Document] = field(default_factory=list)
    problems: list[LoadProblem] = field(default_factory=list)
