"""project-index の読み取り API と端末の設定の API の応答の型。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from dev_docs.shared.errors import ProjectIndexResponseError, Violation

type SourceStateKind = Literal["serving", "not_served", "disabled", "pending_reload"]
type FailureReason = Literal["timeout", "exit", "not_runnable", "invalid_yaml"]

REQUIRED_DOCUMENT_KEYS = ("id", "kind", "path", "version")
LISTED_METADATA_KEYS = ("id", "kind", "name", "description", "tags", "visibility")


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexedDocument:
    """project-index が返却した 1 件の文書（ファイル 1 つか `records` の要素 1 つ）。"""

    id: str
    kind: str
    source_id: str
    path: str
    data: dict[str, Any]
    metadata: dict[str, Any]
    version: str
    record_index: int | None = None
    body: str = ""
    body_path: str | None = None
    updated: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentRow:
    """配信元の設定の `documents[]` の有効な 1 行のうち、画面が使用するキー。"""

    id: str
    paths: list[str]
    schema: dict[str, Any]
    title: str | None = None
    records: str | None = None
    search: bool = True
    converter: str | None = None
    alias_type: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceView:
    """`GET /sources/{source}/config` の応答。配信元の設定のうち画面が使用するキー。"""

    id: str
    git: bool
    default_ref: str | None
    documents: list[DocumentRow]
    nav: dict[str, Any] | None = None
    decision_folders: list[str] = field(default_factory=list)
    diff_ignore_keys: list[str] = field(default_factory=lambda: ["updated"])
    github_repository: str | None = None
    github_issue_labels: list[str] = field(default_factory=list)

    def row(self, kind: str) -> DocumentRow | None:
        """行の ID から `DocumentRow` を返却する（無ければ `None`）。"""
        return next((row for row in self.documents if row.id == kind), None)

    def record_kinds(self) -> set[str]:
        """`records` を持つ文書の行の ID を返却する。"""
        return {row.id for row in self.documents if row.records is not None}


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexFailure:
    """project-index が返却した、変換か読み込みの失敗。"""

    reason: FailureReason
    kind: str
    detail: str = ""
    script: str | None = None
    file: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentList:
    """`GET /sources/{source}/docs` の応答。"""

    ref: str | None
    documents: list[IndexedDocument]


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentDetail:
    """`GET /sources/{source}/docs/{path}` の応答。"""

    document: IndexedDocument | None
    markdown: str | None = None
    failure: IndexFailure | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceState:
    """配信元 1 つの状態。"""

    id: str | None
    status: SourceStateKind
    errors: list[Violation] = field(default_factory=list)
    config: list[str] = field(default_factory=list)
    config_version: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionIndex:
    """`GET /sources/{source}/decisions` の応答。"""

    counts: dict[str, int]

    @property
    def linkable(self) -> set[str]:
        """該当するフォルダがちょうど 1 つの ID を返却する。"""
        return {decision for decision, count in self.counts.items() if count == 1}


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchHit:
    """検索の結果の 1 件。"""

    id: str
    path: str
    name: str
    snippets: list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchHits:
    """`GET /sources/{source}/search` の応答。"""

    total_count: int
    items: list[SearchHit]


@dataclass(frozen=True, slots=True, kw_only=True)
class NamedRef:
    """ブランチかタグ 1 つ。"""

    name: str
    commit: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitSummary:
    """最近の commit 1 つ。"""

    commit: str
    date: datetime
    subject: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RefList:
    """`GET /sources/{source}/refs` の応答。"""

    git: bool
    default_ref: str
    branches: list[NamedRef] = field(default_factory=list)
    tags: list[NamedRef] = field(default_factory=list)
    commits: list[CommitSummary] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class SettingsSourcesView:
    """`GET`・`PUT /settings/sources` の応答。"""

    settings_path: str
    rows: list[dict[str, Any]]
    states: list[SourceState]
    # 照合つきの保存の `expected_version` に指定する内容のバージョン
    version: str | None = None


def parse_datetime(value: Any) -> datetime | None:
    """ISO 8601 の日時を読む（無いか読めなければ `None`）。"""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_document(
    source_id: str, value: Mapping[str, Any], *, record_index: int | None = None
) -> IndexedDocument:
    """project-index の文書の一覧の 1 件を `IndexedDocument` にする。"""
    for key in REQUIRED_DOCUMENT_KEYS:
        if key not in value:
            raise ProjectIndexResponseError(
                message=f"project-index の応答に {key} がありません",
                summary=f"project-index の応答に {key} がありません",
            )
    return IndexedDocument(
        id=str(value["id"]),
        kind=str(value["kind"]),
        source_id=source_id,
        path=str(value["path"]),
        data=dict(value.get("value") or {}),
        metadata={key: value.get(key) for key in LISTED_METADATA_KEYS},
        version=str(value["version"]),
        record_index=record_index,
        body_path=value.get("bodyPath"),
    )
