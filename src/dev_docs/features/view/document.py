"""文書の取得。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from dev_docs.features.changes.compare import changed_keys
from dev_docs.features.convert.decisions import DECISION_PAGE_PREFIX, decision_page_id
from dev_docs.features.convert.embed import embed_paths
from dev_docs.features.convert.types import ConvertFailure
from dev_docs.features.documents.aliases import collect_aliases
from dev_docs.features.view.document_lists import CachedDocumentList, resolve_commit
from dev_docs.features.view.edit import DocumentEdit, build_document_edit
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
from dev_docs.integrations.project_index.client import build_source_view
from dev_docs.integrations.project_index.types import (
    DecisionIndex,
    DocumentList,
    IndexedDocument,
    IndexFailure,
    RefList,
    SettingsSourcesView,
    SourceView,
    parse_document_list,
)
from dev_docs.shared.errors import (
    DevDocsError,
    DocumentNotFoundError,
    ProjectIndexUnreachableError,
    RefNotFoundError,
    SourceNotServedError,
    UnknownSourceError,
)

if TYPE_CHECKING:
    from dev_docs.main import Handlers

logger = logging.getLogger(__name__)

# 文書の取得全体を打ち切る秒数（非機能要件の document_fetch_timeout）
DOCUMENT_FETCH_TIMEOUT_SEC: float = 70


def _aliases(view: SourceView, documents: Sequence[IndexedDocument]) -> list[AliasItem]:
    """`alias_type` を持つ行の文書のエイリアスを応答の構造にする。"""
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


async def _unreadable(
    handlers: Handlers, source_id: str, path: str, ref: str | None
) -> IndexFailure | None:
    """文書の一覧に無いページのパスが、YAML を読み込めないファイルなら、その失敗を返却する。"""
    try:
        detail = await handlers.project_index.document(source_id, path, ref=ref)
    except DocumentNotFoundError:
        return None
    failure = detail.failure
    if failure is not None and failure.reason == "invalid_yaml":
        return failure
    return None


def _activate(tabs: list[NavTab], path: str | None) -> list[NavTab]:
    """返却した文書を含むタブの `active` を `True` にする。"""
    return [
        tab.model_copy(update={"active": path is not None and path in _pages(tab.items)})
        for tab in tabs
    ]


def _updated_at(view: SourceView, document: IndexedDocument) -> datetime:
    """文書の更新日時（無ければ今の日時）を返却する。"""
    if document.updated is not None:
        return document.updated
    logger.warning("更新日時が無い（%s・%s）", view.id, document.path)
    return datetime.now(tz=UTC)


async def _document_list(
    handlers: Handlers,
    source_id: str,
    ref: str | None,
    refs: Awaitable[RefList],
    view: Awaitable[SourceView],
) -> DocumentList:
    """リビジョンの文書の一覧を、文書の一覧の保持か project-index から取り出す。"""
    client = handlers.project_index
    cache = handlers.document_lists
    commit = resolve_commit(await refs, ref)
    # commit に解決できない（Git 管理外・HEAD~1 など）: 保持せずに毎回問い合わせる
    if commit is None:
        value = await client.fetch_document_list(source_id, ref=ref)
        resolved = await view
        return await asyncio.to_thread(
            parse_document_list, source_id, value, record_kinds=resolved.record_kinds()
        )
    cached = cache.get(source_id, commit)
    # 保持がある: 配信元の設定が同じなら保持を使用し、違えば捨てて取得し直す
    if cached is not None:
        resolved = await view
        if resolved.config_hash == cached.config_hash:
            return cached.documents
        cache.discard(source_id, commit)
    # 同じ組を取得中ならその問い合わせを共有し、配信元の設定の応答を待たずに問い合わせる
    value = await cache.fetch(
        source_id, commit, lambda: client.fetch_document_list(source_id, ref=commit)
    )
    resolved = await view
    documents = await asyncio.to_thread(
        parse_document_list, source_id, value, record_kinds=resolved.record_kinds()
    )
    cache.put(
        source_id,
        commit,
        CachedDocumentList(config_hash=resolved.config_hash, documents=documents),
    )
    return documents


async def _diff(
    handlers: Handlers,
    view: SourceView,
    document: IndexedDocument,
    tabs: list[NavTab],
    documents: Sequence[IndexedDocument],
    diff_ref: str,
    refs: Awaitable[RefList],
    view_task: Awaitable[SourceView],
) -> tuple[DocumentDiff, list[NavTab]]:
    """`diff_ref` と比べた差分の結果と、サイドバーの変化を付けたタブを作る。"""
    base = await _document_list(handlers, view.id, diff_ref, refs, view_task)
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


async def _settings_if_default(
    handlers: Handlers, ref: str | None, refs: Awaitable[RefList]
) -> SettingsSourcesView | None:
    """既定のブランチを指した要求だけ、端末の設定の配信元の行を問い合わせる（それ以外は `None`）。"""
    resolved = await refs
    if ref is not None and ref != resolved.default_ref:
        return None
    return await handlers.project_index.settings_sources()


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
    """配信元の文書を変換した Markdown と、タブ・差分の項目・列の設定を返却する。"""
    # 文書の取得全体の制限時間。途中の問い合わせも取り消すため、問い合わせごとの制限時間は残り時間を超えない
    limit = DOCUMENT_FETCH_TIMEOUT_SEC
    try:
        async with asyncio.timeout(limit):
            return await _get_document(
                source_id, path, handlers=handlers, ref=ref, diff_ref=diff_ref
            )
    except TimeoutError as error:
        raise ProjectIndexUnreachableError(
            address=handlers.project_index.address,
            reason=f"{limit:g} 秒以内に応答がありませんでした",
            kind="timeout",
        ) from error


async def _get_document(
    source_id: str,
    path: str | None,
    *,
    handlers: Handlers,
    ref: str | None,
    diff_ref: str | None,
) -> DocumentResponse:
    """文書の取得の本体（制限時間の外側は `get_document` が持つ）。"""
    client = handlers.project_index

    async def _view() -> SourceView:
        return build_source_view(source_id, await config_task, await refs_task)

    # 配信元の設定とリビジョンを同時に問い合わせ、文書の一覧はリビジョンの応答の後すぐに問い合わせる
    try:
        async with asyncio.TaskGroup() as group:
            refs_task = group.create_task(client.refs(source_id, commits=0))
            config_task = group.create_task(client.source_config(source_id))
            view_task = group.create_task(_view())
            listed_task = group.create_task(
                _document_list(handlers, source_id, ref, refs_task, view_task)
            )
            settings_task = group.create_task(_settings_if_default(handlers, ref, refs_task))
    except ExceptionGroup as group_error:
        # 呼び出し元へは最初の例外（UnknownSourceError など）をそのまま伝える
        raise group_error.exceptions[0] from None
    view = view_task.result()
    listed = listed_task.result()
    settings = settings_task.result()
    # 本文を編集できる要求: 文書を既定のブランチの先頭のコミットで取得し、その内容を編集の元にする
    edit_commit = resolve_commit(refs_task.result(), None) if settings is not None else None
    response_ref = (ref if ref is not None else view.default_ref) if view.git else None
    tabs = build_nav(view, listed.documents)
    columns = await asyncio.to_thread(handlers.columns.get, view.id)
    github = (
        GitHubTarget(repository=view.github_repository, issue_labels=list(view.github_issue_labels))
        if view.github_repository
        else None
    )

    # 検討事項の文書のパス: 話し合いの記録のフォルダの文書を変換せずに返却する
    decision = decision_page_id(path) if path is not None else None
    if decision is not None:
        decision_markdown = await client.decision(view.id, decision)
        return DocumentResponse(
            source=view.id,
            ref=response_ref,
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

    # 返却する文書を決める
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
        broken = await _unreadable(handlers, view.id, path, ref)
        if broken is None:
            raise DocumentNotFoundError(message=f"文書がありません: {path}", missing=[path])
        # YAML を読み込めない: 変換せずに読み込めなかった位置を返却する
        return DocumentResponse(
            source=view.id,
            ref=response_ref,
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
        ref=edit_commit if edit_commit is not None else ref,
        document_id=document.id if document.record_index is not None else None,
    )
    if view.decision_folders:
        detail, decisions = await asyncio.gather(detail_task, client.decisions(view.id))
    else:
        detail, decisions = await detail_task, DecisionIndex(counts={})
    item_ranges: list[tuple[str, str]] = []
    rendered = await asyncio.to_thread(
        handlers.converter.render,
        view,
        detail,
        listed.documents,
        linkable=decisions.linkable,
        item_ranges=item_ranges,
    )
    markdown: str | None = None
    table_keys: list[str] = []
    conversion_error: ConversionError | None = None
    edit: DocumentEdit | None = None
    if isinstance(rendered, ConvertFailure):
        conversion_error = _conversion_error(rendered)
    else:
        embedded = await _embedded(handlers, view.id, rendered, ref)
        converted = handlers.converter.finish(rendered, document.kind, embedded)
        markdown = converted.markdown
        table_keys = list(converted.table_keys)
        # 本文を編集できる要求: 項目の範囲も本文と同じく仕上げて、編集の情報を組み立てる
        if settings is not None and edit_commit is not None:
            finished = [
                (item, handlers.converter.finish(text, document.kind, embedded).markdown.strip())
                for item, text in item_ranges
            ]
            edit = build_document_edit(
                view,
                config_task.result().value,
                detail,
                write_api_kinds=settings.write_api_kinds.get(view.id, []),
                base_commit=edit_commit,
                version=document.version,
                item_ranges=finished,
            )

    # diff が指定された Git の配信元は、差分の結果とサイドバーの変化を求める
    diff: DocumentDiff | None = None
    if diff_ref is not None and view.git:
        diff, tabs = await _diff(
            handlers, view, document, tabs, listed.documents, diff_ref, refs_task, view_task
        )
    return DocumentResponse(
        source=view.id,
        ref=response_ref,
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
        updated_at=_updated_at(view, detail.document or document),
        edit=edit,
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
