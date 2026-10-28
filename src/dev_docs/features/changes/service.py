"""`list_changes` の処理。"""

from __future__ import annotations

from datetime import date
from typing import Any

from dev_docs.features.access.service import resolve_read_targets
from dev_docs.features.access.types import Target
from dev_docs.features.changes.compare import changed_keys, diff_lines
from dev_docs.features.changes.types import (
    LAST_READ_LABEL,
    WORKTREE_LABEL,
    ChangeItem,
    ChangesRequest,
    ChangesResult,
    RangePoint,
)
from dev_docs.features.documents.loader import documents_from_text
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.features.history.query import changed_files, read_file_at, resolve_ref
from dev_docs.features.search.cursor import decode_cursor, encode_cursor
from dev_docs.features.search.fields import known_fields
from dev_docs.features.search.filters import check_filter, match_filter
from dev_docs.features.search.types import LIMIT_MAX, MAX_CHARS_LIMIT, SearchRequest
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.seen.types import SessionKey
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.shared.errors import InvalidArgumentError, LastReadNotFoundError, Violation
from dev_docs.shared.hashing import value_hash

SHORT_COMMIT = 7
MULTI_SOURCE_MIN = 2
BODY = "body"


def _invalid(violations: list[Violation]) -> InvalidArgumentError:
    """引数の違反を `InvalidArgumentError` にする。"""
    return InvalidArgumentError(
        message=f"引数が正しくありません: {len(violations)} 件", violations=violations
    )


def _content(document: Document, markdown: bool) -> dict[str, Any]:
    """比べる内容（Markdown の文書は `body` も 1 つのキーにする）。"""
    return {**document.data, BODY: document.body} if markdown else dict(document.data)


def _range_documents(
    target: Target, request: ChangesRequest
) -> tuple[dict[str, Document], dict[str, Document], RangePoint, RangePoint]:
    """区間の前と後の文書を、ID → 文書で作る。"""
    source = target.source
    repo_root = source.repo_root or source.root
    work_root = target.worktree or repo_root
    prefix = source.root.relative_to(repo_root).as_posix()
    default_ref = source.config.default_ref
    assert request.from_ is not None  # noqa: S101
    start = resolve_ref(repo_root, request.from_, date_base=default_ref, argument="from")
    end = (
        resolve_ref(repo_root, request.to, date_base=default_ref, argument="to")
        if request.to is not None
        else None
    )
    changes = changed_files(work_root, start.commit, end.commit if end else None)
    before: dict[str, Document] = {}
    after: dict[str, Document] = {}
    for change in changes:
        if prefix != "." and not change.path.startswith(f"{prefix}/"):
            continue
        relative = change.path if prefix == "." else change.path.removeprefix(f"{prefix}/")
        table = next(
            (
                row
                for row in source.config.documents
                if row.enabled and row.matches(relative)
            ),
            None,
        )
        if table is None:
            continue
        old_text = read_file_at(work_root, start.commit, change.path)
        if end is not None:
            new_text = read_file_at(work_root, end.commit, change.path)
        else:
            current = work_root / change.path
            new_text = current.read_text(encoding="utf-8") if current.is_file() else None
        for text, bucket in ((old_text, before), (new_text, after)):
            if text is None:
                continue
            documents, _ = documents_from_text(
                text, source.root, relative, table, source_id=source.id
            )
            bucket.update({document.id: document for document in documents})
    from_point = RangePoint(request.from_, start.commit[:SHORT_COMMIT], start.date)
    to_point = (
        RangePoint(request.to or "", end.commit[:SHORT_COMMIT], end.date)
        if end is not None
        else RangePoint(WORKTREE_LABEL)
    )
    return before, after, from_point, to_point


def list_changes(
    request: ChangesRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    seen: SeenStore,
) -> ChangesResult:
    """`list_changes` の要求を処理して変更の結果を返す。"""
    if request.to is not None and request.from_ is None:
        raise _invalid(
            [Violation(path="to", rule="to には from が要ります", fix="from も渡してください")]
        )
    targets = resolve_read_targets(
        registry=registry,
        source=request.source,
        worktree=request.worktree,
        cwd=request.cwd,
    )
    if request.from_ is not None:
        for target in targets:
            if not target.source.is_git:
                raise _invalid(
                    [
                        Violation(
                            path="from",
                            rule=f"{target.source.id} は Git の管理外なので区間を指せません",
                            fix="from を省くと、この会話で前回読んだ時点からの変更を返します",
                        )
                    ]
                )
    key = SessionKey.of(request.session_id, request.agent_id)
    notes: list[str] = []
    fields = known_fields(
        store.schema(target, table.id)
        for target in targets
        for table in target.source.config.documents
        if table.enabled and table.type == "yaml"
    )
    violations = check_filter(SearchRequest(filter=request.filter, order_by=[]), fields)
    if violations:
        raise _invalid(violations)
    entries: list[tuple[int, Target, ChangeItem, Document]] = []
    points: list[tuple[RangePoint, RangePoint]] = []
    any_last_read = False
    for index, target in enumerate(targets):
        source = target.source
        markdown_of = {row.id: row.type == "markdown" for row in source.config.documents}
        if request.from_ is not None:
            before, after, from_point, to_point = _range_documents(target, request)
        else:
            last = seen.last_read(key, source.id)
            any_last_read = any_last_read or bool(last)
            before = {}
            for doc_id, record in last.items():
                table = next((r for r in source.config.documents if r.id == record.doc_kind), None)
                if table is None:
                    continue
                path = f"{doc_id}.md" if table.type == "markdown" else f"{doc_id}.yaml"
                found, _ = documents_from_text(
                    record.content, target.base, path, table, source_id=source.id
                )
                # 記録の文書の ID は、読んだときの ID に合わせる
                before.update({doc_id: found[0]} if found else {})
            current = {document.id: document for document in store.load(target).documents}
            after = {doc_id: current[doc_id] for doc_id in last if doc_id in current}
            earliest = min((record.read_at for record in last.values()), default=None)
            from_point = RangePoint(LAST_READ_LABEL, None, earliest)
            to_point = RangePoint(WORKTREE_LABEL)
        points.append((from_point, to_point))
        for doc_id in sorted({*before, *after}):
            old, new = before.get(doc_id), after.get(doc_id)
            kind_source = new or old
            assert kind_source is not None  # noqa: S101
            markdown = markdown_of.get(kind_source.kind, False)
            ignore = source.config.diff_ignore_keys
            values = changed_keys(
                _content(old, markdown) if old else {},
                _content(new, markdown) if new else {},
                ignore=ignore,
            )
            if old is None:
                change = "added"
            elif new is None:
                change = "deleted"
            elif values:
                change = "modified"
            else:
                continue
            keys = list(values)
            judged = new or old
            assert judged is not None  # noqa: S101
            if not match_filter(request.filter, judged, fields=fields, today=date.today()):  # noqa: DTZ011
                continue
            diff = (
                diff_lines(old.body if old else "", new.body if new else "")
                if request.view == "full"
                else None
            )
            location = (
                store.location(target, new) if request.to is None and new is not None else None
            )
            item = ChangeItem(
                id=doc_id,
                source=source.id if len(targets) >= MULTI_SOURCE_MIN else None,
                change=change,  # type: ignore[arg-type]
                keys=keys,
                values=values,
                diff=diff,
                path=location,
                scope=(("section" if request.view == "full" else "summary") if location else None),
            )
            entries.append((index, target, item, judged))
    if request.from_ is None and not any_last_read:
        raise LastReadNotFoundError(
            message="この会話で読んだ記録がありません。from を渡してください",
            next_steps=["from に commit やブランチを渡してください"],
        )
    limit = request.limit
    if limit < 1:
        raise _invalid([Violation(path="limit", rule="1 以上にしてください")])
    if limit > LIMIT_MAX:
        limit = LIMIT_MAX
        notes.append(f"limit {request.limit} は上限 {LIMIT_MAX} に丸めました")
    max_chars = request.max_chars
    if max_chars > MAX_CHARS_LIMIT:
        max_chars = MAX_CHARS_LIMIT
        notes.append(f"max_chars {request.max_chars} は上限 {MAX_CHARS_LIMIT} に丸めました")
    entries.sort(key=lambda entry: (entry[0], entry[2].id))
    fingerprint = value_hash(
        request.model_dump(mode="json", exclude={"cursor", "limit", "max_chars"}, by_alias=True)
    )
    start = decode_cursor(request.cursor, fingerprint) if request.cursor else 0
    window = entries[start : start + limit]
    items: list[ChangeItem] = []
    size = 0
    truncated = False
    for _, _, item, _ in window:
        item_size = len(item.id) + sum(len(key) for key in item.keys) + len(item.diff or "")
        if items and size + item_size > max_chars:
            truncated = True
            break
        items.append(item)
        size += item_size
    next_position = start + len(items)
    next_cursor = (
        encode_cursor(next_position, fingerprint) if next_position < len(entries) else None
    )
    if truncated:
        notes.append(f"max_chars {max_chars} で打ち切りました。cursor を渡すと続きを取れます")
    if len(points) >= MULTI_SOURCE_MIN:
        for target, (from_point, to_point) in zip(targets, points, strict=True):
            notes.insert(
                0,
                f"{target.source.id}: {from_point.commit or from_point.input} → "
                f"{to_point.commit or to_point.input}",
            )
    return ChangesResult(
        range_from=points[0][0],
        range_to=points[0][1],
        total_count=len(entries),
        items=items,
        next_cursor=next_cursor,
        truncated=truncated,
        notes=notes,
    )
