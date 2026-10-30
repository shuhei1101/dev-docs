"""配信元の設定と配信中の配信元の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from dev_docs.shared.errors import UnknownKindError, Violation

SOURCE_CONFIG_VERSION = "2"

type SourceStatusKind = Literal["serving", "not_served", "disabled"]


@dataclass(frozen=True)
class DocumentTable:
    """配信元の設定の `documents[]` の 1 行。"""

    id: str
    paths: list[str]
    schema_path: str
    title: str | None = None
    enabled: bool = True
    validators: list[str] = field(default_factory=list)
    converter: str | None = None
    writable: bool | None = None
    after_write: list[str] = field(default_factory=list)
    search: bool = True
    records: str | None = None
    body_file: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    exclude: list[str] = field(default_factory=list)
    alias_type: str | None = None

    @property
    def is_writable(self) -> bool:
        """`write_docs`・`delete_docs` を許すか（`writable` が無ければ許す）。"""
        return True if self.writable is None else self.writable

    def excludes(self, path: str) -> bool:
        """ファイル名（パスの末尾の要素）が `exclude` のどれかに当たるか。"""
        name = PurePosixPath(PurePosixPath(path).name)
        return any(name.full_match(pattern) for pattern in self.exclude)

    def matches(self, path: str) -> bool:
        """ファイルがこの行の文書になるか（`paths` に当たり、`exclude` に当たらない）。"""
        target = PurePosixPath(path)
        in_paths = any(target.full_match(pattern) for pattern in self.paths)
        return in_paths and not self.excludes(path)


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
        default_factory=lambda: ["references", "depends_on", "see_also", "implements", "tests"]
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
        enabled = [row for row in self.config.documents if row.enabled]
        for row in enabled:
            if row.id == kind:
                return row
        raise UnknownKindError(
            message=f"{self.id}: 種類 {kind} はありません",
            kinds=[row.id for row in enabled],
            next_steps=["describe(source) で種類の一覧を見てください"],
        )

    def script(
        self, table: Literal["validators", "converters", "generators"], script_id: str
    ) -> ScriptEntry:
        """検査・変換・生成の行を ID で引く。"""
        for row in getattr(self.config, table):
            if row.id == script_id:
                return row  # type: ignore[no-any-return]
        raise KeyError(f"{table}[{script_id}]")


@dataclass(frozen=True)
class SourceStatus:
    """端末の設定の 1 行が配信中か、外したならその理由。"""

    id: str
    index: int
    status: SourceStatusKind
    errors: list[Violation] = field(default_factory=list)
    config_version: tuple[str, str] | None = None
    config: tuple[str, ...] = ()
