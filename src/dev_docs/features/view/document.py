"""文書の取得。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, Literal

from dev_docs.features.changes.compare import changed_keys
from dev_docs.features.convert.decisions import DECISION_PAGE_PREFIX, decision_page_id
from dev_docs.features.convert.embed import embed_paths
from dev_docs.features.convert.types import ConvertFailure
from dev_docs.features.documents.aliases import collect_aliases
from dev_docs.features.view.nav import build_nav, first_page, mark_nav_changes
from dev_docs.features.view.paths import find_page, page_path
from dev_docs.features.view.types import (
    AliasItem,
    ConversionError,
    DocumentDiff,
    DocumentResponse,
    GitHubTarget,
    NavItem,
    NavTab,
)
from dev_docs.integrations.project_index.types import (
    DecisionIndex,
    IndexedDocument,
    IndexFailure,
    SourceView,
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

logger = logging.getLogger(__name__)


def _aliases(view: SourceView, documents: Sequence[IndexedDocument]) -> list[AliasItem]:
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
        for entry in collect_aliases(view, documents).entries
    ]


def _pages(items: Sequence[NavItem]) -> list[str]:
    """サイドバーの項目から、文書のページのパスを並べる。"""
    pages: list[str] = []
    for item in items:
        if item.kind == "page" and item.path is not None:
            pages.append(item.path)
        pages.extend(_pages(item.items))
    return pages


def _unreadable(problems: Sequence[IndexFailure], path: str) -> IndexFailure | None:
    """拡張子を落としたパスが `path` と同じ、YAML を読めなかったファイルを探す。"""
    return next(
        (
            problem
            for problem in problems
            if problem.file is not None
            and PurePosixPath(problem.file).with_suffix("").as_posix() == path
        ),
        None,
    )


def _activate(tabs: list[NavTab], path: str | None) -> list[NavTab]:
    """返した文書を含むタブの `active` を `True` にする。"""
    return [
        tab.model_copy(update={"active": path is not None and path in _pages(tab.items)})
        for tab in tabs
    ]


def _updated_at(view: SourceView, document: IndexedDocument) -> datetime:
    """文書の更新日時（無ければ今の日時）を返す。"""
    if document.updated is not None:
        return document.updated
    logger.warning("更新日時が無い（%s・%s）", view.id, document.path)
    return datetime.now(tz=UTC)


async def _diff(
    handlers: Handlers,
    view: SourceView,
    document: IndexedDocument,
    tabs: list[NavTab],
    documents: Sequence[IndexedDocument],
    diff_ref: str,
) -> tuple[DocumentDiff, list[NavTab]]:
    """`diff_ref` と比べた差分の結果と、サイドバーの変化を付けたタブを作る。"""
    base = await handlers.project_index.list_documents(view.id, ref=diff_ref)
    before = next((d for d in base.documents if d.id == document.id), None)
    change: Literal["added", "modified"] | None
    if before is None:
        change = "added"
        changed: list[str] = []
    elif before.version != document.version:
        change = "modified"
        changed = list(changed_keys(before.data, document.data, ignore=view.diff_ignore_keys))
    else:
        change = None
        changed = []
    marked = mark_nav_changes(
        tabs,
        build_nav(view, base.documents),
        versions={page_path(d): d.version for d in documents},
        base_versions={page_path(d): d.version for d in base.documents},
    )
    return DocumentDiff(base=diff_ref, change=change, changed_items=changed), marked


async def _embedded(
    handlers: Handlers, source_id: str, markdown: str, ref: str | None
) -> dict[str, Any | None]:
    """埋め込みのマーカーのパスごとに、project-index から文書の値を取る。"""
    paths = embed_paths(markdown)

    async def fetch(path: str) -> Any | None:
        try:
            detail = await handlers.project_index.document(source_id, path, ref=ref)
        except DocumentNotFoundError:
            return None
        return None if detail.document is None else detail.document.data

    values = await asyncio.gather(*(fetch(path) for path in paths))
    return dict(zip(paths, values, strict=True))


def _conversion_error(failure: IndexFailure | ConvertFailure) -> ConversionError:
    """失敗を応答の `conversionError` にする。"""
    return ConversionError(
        reason=failure.reason,
        kind=failure.kind,
        detail=failure.detail,
        script=failure.script,
        file=failure.file,
        line=failure.line,
        column=failure.column,
    )


async def get_document(
    source_id: str,
    path: str | None,
    *,
    handlers: Handlers,
    ref: str | None,
    diff_ref: str | None,
) -> DocumentResponse:
    """配信元の文書を変換した Markdown と、タブ・差分の項目・列の設定を返す。"""
    client = handlers.project_index
    view, listed = await asyncio.gather(
        client.source_view(source_id), client.list_documents(source_id, ref=ref)
    )
    tabs = build_nav(view, listed.documents)
    columns = await asyncio.to_thread(handlers.columns.get, view.id)
    github = (
        GitHubTarget(repository=view.github_repository, issue_labels=list(view.github_issue_labels))
        if view.github_repository
        else None
    )

    # 検討事項の文書のパス: 話し合いの記録のフォルダの文書を変換せずに返す
    decision = decision_page_id(path) if path is not None else None
    if decision is not None:
        decision_markdown = await client.decision(view.id, decision)
        return DocumentResponse(
            source=view.id,
            ref=listed.ref,
            path=f"{DECISION_PAGE_PREFIX}{decision}",
            body_path=None,
            markdown=decision_markdown,
            conversion_error=None,
            tabs=_activate(tabs, None),
            github=github,
            columns=columns,
            table_keys=[],
            diff=None,
            updated_at=datetime.now(tz=UTC),
        )

    # 返す文書を決める
    document: IndexedDocument | None
    if path is None:
        first = next((page for tab in tabs if (page := first_page(tab)) is not None), None)
        if first is None:
            raise DocumentNotFoundError(message="文書がありません", missing=[])
        path = first
        document = find_page(listed.documents, first)
    else:
        document = find_page(listed.documents, path)
    if document is None:
        broken = _unreadable(listed.unreadable, path)
        if broken is None:
            raise DocumentNotFoundError(message=f"文書がありません: {path}", missing=[path])
        # YAML を読めない: 変換せずに読めなかった位置を返す
        return DocumentResponse(
            source=view.id,
            ref=listed.ref,
            path=path,
            body_path=None,
            markdown=None,
            conversion_error=_conversion_error(broken),
            tabs=_activate(tabs, None),
            github=github,
            columns=columns,
            table_keys=[],
            diff=None,
            updated_at=datetime.now(tz=UTC),
        )

    # 文書の詳細と検討事項の一覧を取り、変換する
    detail_task = client.document(
        view.id,
        document.path,
        ref=ref,
        document_id=document.id if document.record_index is not None else None,
    )
    if view.decision_folders:
        detail, decisions = await asyncio.gather(detail_task, client.decisions(view.id))
    else:
        detail, decisions = await detail_task, DecisionIndex(counts={})
    rendered = await asyncio.to_thread(
        handlers.converter.render,
        view,
        detail,
        listed.documents,
        linkable=decisions.linkable,
    )
    markdown: str | None = None
    table_keys: list[str] = []
    conversion_error: ConversionError | None = None
    if isinstance(rendered, ConvertFailure):
        conversion_error = _conversion_error(rendered)
    else:
        embedded = await _embedded(handlers, view.id, rendered, ref)
        converted = handlers.converter.finish(rendered, document.kind, embedded)
        markdown = converted.markdown
        table_keys = list(converted.table_keys)

    # diff が指定された Git の配信元は、差分の結果とサイドバーの変化を求める
    diff: DocumentDiff | None = None
    if diff_ref is not None and view.git:
        diff, tabs = await _diff(handlers, view, document, tabs, listed.documents, diff_ref)
    return DocumentResponse(
        source=view.id,
        ref=listed.ref,
        path=page_path(document),
        body_path=document.body_path,
        markdown=markdown,
        conversion_error=conversion_error,
        tabs=_activate(tabs, page_path(document)),
        github=github,
        columns=columns,
        table_keys=table_keys,
        aliases=[] if conversion_error is not None else _aliases(view, listed.documents),
        diff=diff,
        updated_at=_updated_at(view, document),
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
