"""文書の取得。"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

from dev_docs.features.access.types import Target
from dev_docs.features.changes.compare import changed_keys
from dev_docs.features.documents.aliases import collect_aliases
from dev_docs.features.documents.types import Document, LoadProblem
from dev_docs.features.sources.types import ServedSource
from dev_docs.features.view.nav import build_nav, first_page, mark_nav_changes
from dev_docs.features.view.paths import find_page, page_path, screen_target
from dev_docs.features.view.types import (
    AliasItem,
    ConversionError,
    DocumentDiff,
    DocumentResponse,
    GitHubTarget,
    NavItem,
    NavTab,
)
from dev_docs.shared.errors import (
    DevDocsError,
    DocumentNotFoundError,
    RefNotFoundError,
    SourceNotServedError,
    UnknownSourceError,
)

if TYPE_CHECKING:
    from dev_docs.main import Handlers


def _aliases(source: ServedSource, documents: Sequence[Document]) -> list[AliasItem]:
    """`alias_type` を持つ行の文書のエイリアスを応答の形にする。"""
    return [
        AliasItem(
            id=entry.id,
            name=entry.name,
            aliases=list(entry.aliases),
            description=entry.description,
            alias_type=entry.alias_type,
            avoid=None if entry.avoid is None else list(entry.avoid),
            **entry.extra,
        )
        for entry in collect_aliases(source, documents).entries
    ]


def _pages(items: Sequence[NavItem]) -> list[str]:
    """サイドバーの項目から、文書のページのパスを並べる。"""
    pages: list[str] = []
    for item in items:
        if item.kind == "page" and item.path is not None:
            pages.append(item.path)
        pages.extend(_pages(item.items))
    return pages


def _unreadable(problems: Sequence[LoadProblem], path: str) -> LoadProblem | None:
    """拡張子を落としたパスが `path` と同じ、YAML を読めなかったファイルを探す。"""
    return next(
        (
            problem
            for problem in problems
            if problem.reason == "unreadable"
            and PurePosixPath(problem.path).with_suffix("").as_posix() == path
        ),
        None,
    )


def _kind_of(source: ServedSource, file: str) -> str:
    """ファイルのパスが当たる文書の行の ID を返す（当たる行が無ければ空）。"""
    for row in source.config.documents:
        if row.matches(file):
            return row.id
    return ""


def _diff(
    handlers: Handlers,
    target: Target,
    document: Document,
    tabs: list[NavTab],
    loaded_documents: Sequence[Document],
    diff_ref: str,
) -> tuple[DocumentDiff, list[NavTab]]:
    """`diff_ref` と比べた差分の結果と、サイドバーの変化を付けたタブを作る。"""
    source = target.source
    base_target, _ = screen_target(source.id, diff_ref, registry=handlers.registry)
    base_documents = handlers.store.load(base_target).documents
    before = next((d for d in base_documents if d.id == document.id), None)
    change: Literal["added", "modified"] | None
    if before is None:
        change = "added"
        changed: list[str] = []
    elif before.version != document.version:
        change = "modified"
        changed = list(
            changed_keys(before.data, document.data, ignore=source.config.diff_ignore_keys)
        )
    else:
        change = None
        changed = []
    marked = mark_nav_changes(
        tabs,
        build_nav(source, base_documents),
        versions={page_path(d): d.version for d in loaded_documents},
        base_versions={page_path(d): d.version for d in base_documents},
    )
    return DocumentDiff(base=diff_ref, change=change, changed_items=changed), marked


def _updated_at(source: ServedSource, document: Document) -> datetime:
    """文書の更新日時（無ければファイルの更新日時）を返す。"""
    if document.updated is not None:
        return document.updated
    return datetime.fromtimestamp((source.root / document.path).stat().st_mtime, tz=UTC)


def _activate(tabs: list[NavTab], path: str | None) -> list[NavTab]:
    """返した文書を含むタブの `active` を `True` にする。"""
    return [
        tab.model_copy(update={"active": path is not None and path in _pages(tab.items)})
        for tab in tabs
    ]


def get_document(
    source_id: str,
    path: str | None,
    *,
    handlers: Handlers,
    ref: str | None,
    diff_ref: str | None,
) -> DocumentResponse:
    """配信元の文書を変換した Markdown と、タブ・差分の項目・列の設定を返す。"""
    # 読む場所を作り、文書を集める
    target, resolved = screen_target(source_id, ref, registry=handlers.registry)
    source = target.source
    loaded = handlers.store.load(target)
    tabs = build_nav(source, loaded.documents)
    # Git の配信元は ref の値（省いたときは default_ref の名前）、Git 管理外は None
    shown_ref = (ref or source.config.default_ref) if source.is_git else None
    columns = handlers.columns.get(source.id)
    github = (
        GitHubTarget(
            repository=source.config.github_repository,
            issue_labels=list(source.config.github_issue_labels),
        )
        if source.config.github_repository
        else None
    )

    # 返す文書を決める
    document: Document | None
    if path is None:
        # path が無い: 一番左のタブの最初の文書
        first = next((page for tab in tabs if (page := first_page(tab)) is not None), None)
        if first is None:
            raise DocumentNotFoundError(message="文書がありません", missing=[])
        path = first
        document = find_page(loaded.documents, first)
    else:
        document = find_page(loaded.documents, path)
    if document is None:
        broken = _unreadable(loaded.problems, path)
        if broken is None:
            raise DocumentNotFoundError(message=f"文書がありません: {path}", missing=[path])
        # YAML を読めない: 変換せずに読めなかった位置を返す
        return DocumentResponse(
            source=source.id,
            ref=shown_ref,
            path=path,
            markdown=None,
            conversion_error=ConversionError(
                reason="invalid_yaml",
                kind=_kind_of(source, broken.path),
                detail=broken.detail,
                file=broken.path,
                line=broken.line,
                column=broken.column,
            ),
            tabs=_activate(tabs, None),
            github=github,
            columns=columns,
            table_keys=[],
            diff=None,
            updated_at=datetime.fromtimestamp((source.root / broken.path).stat().st_mtime, tz=UTC),
        )

    # 文書を変換する
    converted = handlers.converter.convert(target, document)
    failure = converted.failure
    # diff が指定された Git の配信元は、差分の結果とサイドバーの変化を求める
    diff: DocumentDiff | None = None
    if diff_ref is not None and source.is_git and resolved is not None:
        diff, tabs = _diff(handlers, target, document, tabs, loaded.documents, diff_ref)
    return DocumentResponse(
        source=source.id,
        ref=shown_ref,
        path=page_path(document),
        markdown=None if failure is not None else converted.markdown,
        conversion_error=(
            ConversionError.model_validate(dataclasses.asdict(failure))
            if failure is not None
            else None
        ),
        tabs=_activate(tabs, page_path(document)),
        github=github,
        columns=columns,
        table_keys=[] if failure is not None else list(converted.table_keys),
        aliases=[] if failure is not None else _aliases(source, loaded.documents),
        diff=diff,
        updated_at=_updated_at(source, document),
    )


def not_found_fields(
    error: DevDocsError, path: str | None, *, source_id: str = ""
) -> dict[str, str] | None:
    """文書の取得の 404 の problem+json に加える `missing` と `value` を作る。"""
    if isinstance(error, UnknownSourceError):
        return {"missing": "source", "value": error.source_id}
    if isinstance(error, SourceNotServedError):
        return {"missing": "not_served", "value": source_id}
    if isinstance(error, RefNotFoundError):
        return {"missing": "ref", "value": error.value}
    if isinstance(error, DocumentNotFoundError):
        return {"missing": "doc", "value": path or ""}
    return None
