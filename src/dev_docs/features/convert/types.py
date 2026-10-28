"""変換の結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

type Shape = Literal["body", "table", "sections", "list", "diagram", "attributes"]
type DiagramKind = Literal["flowchart", "dataflow", "architecture", "state", "er"]


@dataclass(frozen=True)
class ConvertFailure:
    """本文の場所にエラーの囲みで出す、変換できなかった理由。"""

    reason: Literal["timeout", "exit", "not_runnable", "invalid_yaml"]
    kind: str
    detail: str
    script: str | None = None
    file: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class Converted:
    """画面に渡す Markdown か、変換の失敗。"""

    markdown: str
    table_keys: list[str] = field(default_factory=list)
    failure: ConvertFailure | None = None
