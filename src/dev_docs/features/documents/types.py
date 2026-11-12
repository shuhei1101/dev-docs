"""エイリアスの型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from dev_docs.shared.errors import Violation

AliasType = Literal["term", "doc", "command", "url", "skill", "tool", "path", "env", "avoid"]


@dataclass(frozen=True, slots=True, kw_only=True)
class AliasEntry:
    """`alias_type` を持つ行の文書 1 件のエイリアスのキーの値。"""

    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str | None = None
    alias_type: AliasType
    avoid: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class AliasCollection:
    """検証に通ったエイリアスと違反。"""

    entries: list[AliasEntry] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    has_alias_rows: bool = False
