"""配信元の設定と配信中の配信元の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from dev_docs.shared.errors import Violation

SOURCE_CONFIG_VERSION = "1"

SourceStatusKind = Literal["serving", "not_served", "disabled"]


@dataclass(frozen=True)
class MetadataMapping:
    """`documents[].metadata` の 1 キーの値の取り方。"""

    type: Literal["ref", "custom"]
    field: str | None = None
    value: Any = None


class DocumentDefaults:
    """`documents[].defaults[]` の 1 行。`paths` 以外のキーは重ねるメタデータ。"""

    def __init__(self, paths: list[str], **extra: Any) -> None:
        self.paths = paths
        self.model_extra = extra


@dataclass(frozen=True)
class DocumentTable:
    """配信元の設定の `documents[]` の 1 行。"""

    id: str
    type: Literal["yaml", "markdown"]
    paths: list[str]
    title: str | None = None
    enabled: bool = True
    schema_path: str | None = None
    validators: list[str] = field(default_factory=list)
    converter: str | None = None
    writable: bool | None = None
    after_write: list[str] = field(default_factory=list)
    search: bool = True
    records: str | None = None
    body_file: str | None = None
    metadata: dict[str, MetadataMapping] = field(default_factory=dict)
    defaults: list[DocumentDefaults] = field(default_factory=list)


@dataclass(frozen=True)
class ScriptEntry:
    """`validators[]`・`converters[]`・`generators[]` の 1 行。"""

    id: str
    run: list[str]
    on: list[Literal["read", "write"]] = field(default_factory=lambda: ["write"])


@dataclass(frozen=True)
class SourceConfig:
    """マージして検証を通した配信元の設定。"""

    name: str
    version: str = SOURCE_CONFIG_VERSION
    enabled: bool = True
    default_ref: str = "develop"
    tags: str | None = None
    visibility: dict[str, Any] | None = None
    worktrees: list[str] = field(default_factory=lambda: ["./.claude/worktrees/*"])
    documents: list[DocumentTable] = field(default_factory=list)
    validators: list[ScriptEntry] = field(default_factory=list)
    converters: list[ScriptEntry] = field(default_factory=list)
    generators: list[ScriptEntry] = field(default_factory=list)
    nav: dict[str, Any] | None = None
    ids_format: str | None = None
    related_types: list[str] = field(
        default_factory=lambda: ["references", "depends_on", "see_also"]
    )
    diff_ignore_keys: list[str] = field(default_factory=lambda: ["updated"])
    github_repository: str | None = None
    github_issue_labels: list[str] = field(default_factory=list)
    description: str = ""
    instructions: str = ""


@dataclass(frozen=True)
class ServedSource:
    """検証を通した 1 つの配信元と、読み書きに要る解いた値。"""

    id: str
    root: Path
    config_files: list[Path]
    config: SourceConfig
    is_git: bool
    repo_root: Path | None
    scope_read: list[str]
    scope_write: list[str]
    worktree_globs: list[str]
    schemas: dict[str, dict[str, Any]]
    tag_master: dict[str, str]

    def table(self, kind: str) -> DocumentTable:
        """種類から有効な文書の行を引く。"""
        raise NotImplementedError

    def script(
        self, table: Literal["validators", "converters", "generators"], script_id: str
    ) -> ScriptEntry:
        """検査・変換・生成の行を ID で引く。"""
        raise NotImplementedError


@dataclass(frozen=True)
class SourceStatus:
    """端末の設定の 1 行が配信中か、外したならその理由。"""

    id: str
    index: int
    status: SourceStatusKind
    errors: list[Violation] = field(default_factory=list)
    config_version: tuple[str, str] | None = None
