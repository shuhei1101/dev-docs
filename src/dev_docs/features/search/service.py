"""`search_docs` の処理。"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from dev_docs.features.access.service import resolve_read_targets
from dev_docs.features.access.types import Target
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.documents.types import Document
from dev_docs.features.search.cursor import decode_cursor, encode_cursor
from dev_docs.features.search.fields import field_values, known_fields
from dev_docs.features.search.filters import (
    check_filter,
    match_filter,
    normalize,
    snippet_lines,
)
from dev_docs.features.search.types import (
    FIELD_CHARS_DEFAULT,
    FIELD_CHARS_FULL,
    LIMIT_MAX,
    MAX_CHARS_LIMIT,
    SUMMARY_FIELDS,
    Condition,
    Group,
    GroupCount,
    OrderKey,
    SearchItem,
    SearchRequest,
    SearchResult,
)
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.seen.types import SEEN_MARK, SessionKey
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.validation.service import DocumentChecker
from dev_docs.shared.errors import InvalidArgumentError, Violation
from dev_docs.shared.hashing import value_hash

NONE_LABEL = "（なし）"
MULTI_SOURCE_MIN = 2
BODY = "body"
ARRAY_FIELDS = ("tags", "related", "aliases", "avoid", "@sections")
FINGERPRINT_EXCLUDED = {"cursor", "limit", "max_chars"}


@dataclass(frozen=True)
class _Hit:
    """条件に当たった文書と、読んだ場所。"""

    target: Target
    document: Document
    source_index: int


def _invalid(violations: list[Violation]) -> InvalidArgumentError:
    """引数の違反を `InvalidArgumentError` にする。"""
    return InvalidArgumentError(
        message=f"引数が正しくありません: {len(violations)} 件",
        violations=violations,
        next_steps=["describe(source, kind) でスキーマを見てください"],
    )


def _leaf_words(node: Condition | Group | None) -> list[str]:
    """条件の木から、本文を探す語（`body`・`*` の条件の値）を集める。"""
    if node is None:
        return []
    if isinstance(node, Group):
        return [word for child in node.all_of or node.any_of or [] for word in _leaf_words(child)]
    if node.field in (BODY, "*") and node.op in ("eq", "prefix", "suffix", "contains", "regex"):
        return [normalize(value) for value in node.values]
    return []


def _sort_value(document: Document, field: str) -> Any:
    """並べ替えに使う値（比べられる型にそろえる。値が無ければ `None`）。"""
    values = field_values(document, field)
    if not values:
        return None
    value = values[0]
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).timestamp()
    if isinstance(value, bool | int | float):
        return float(value)
    return unicodedata.normalize("NFKC", str(value)).casefold()


def _order(hits: list[_Hit], request: SearchRequest) -> list[_Hit]:
    """`order_by` の順に並べる（値が無い文書は向きによらず末尾）。"""
    ordered = sorted(hits, key=lambda hit: (hit.source_index, hit.document.id))
    for key in reversed(request.order_by):
        present = [hit for hit in ordered if _sort_value(hit.document, key.field) is not None]
        missing = [hit for hit in ordered if _sort_value(hit.document, key.field) is None]
        present.sort(
            key=lambda hit, field=key.field: (  # type: ignore[misc]
                isinstance(_sort_value(hit.document, field), str),
                _sort_value(hit.document, field),
            ),
            reverse=key.direction == "desc",
        )
        ordered = [*present, *missing]
    return ordered


def _id_ordered(ordered: list[_Hit], request: SearchRequest) -> list[_Hit]:
    """`order_by` が無く `filter` が `id` の `eq` の条件 1 つのときは、その `values` の順にする。"""
    condition = request.filter
    if (
        request.order_by != [OrderKey(field="id")]
        or not isinstance(condition, Condition)
        or condition.field != "id"
        or condition.op != "eq"
    ):
        return ordered
    position = {document_id: index for index, document_id in enumerate(condition.values)}
    return sorted(ordered, key=lambda hit: position.get(hit.document.id, len(position)))


def _groups(hits: Sequence[_Hit], field: str) -> list[GroupCount]:
    """値ごとの件数を、件数の降順・値の昇順で返す。"""
    counts: dict[str, int] = {}
    for hit in hits:
        values = field_values(hit.document, field) or [NONE_LABEL]
        for value in dict.fromkeys(str(item) for item in values):
            counts[value] = counts.get(value, 0) + 1
    return [
        GroupCount(value=value, count=count)
        for value, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _cut(value: Any, limit: int) -> Any:
    """長い文字列を末尾で切り、残りの文字数を添える。"""
    if isinstance(value, str) and len(value) > limit:
        return f"{value[:limit]}…（残り {len(value) - limit} 文字）"
    return value


def _field_value(document: Document, field: str) -> Any:
    """項目の値を返す（配列の項目と複数の値は配列、無ければ `None`）。"""
    values = field_values(document, field)
    if not values:
        return None
    return values if len(values) > 1 or field in ARRAY_FIELDS else values[0]


def _field_names(request: SearchRequest, document: Document) -> list[str]:
    """文書ごとに返す項目の名前を決める。"""
    if request.view == "ids":
        names: list[str] = []
    elif request.view == "summary":
        names = list(SUMMARY_FIELDS)
    else:
        names = [
            *SUMMARY_FIELDS,
            BODY,
            *(key for key in document.metadata if key not in SUMMARY_FIELDS),
        ]
    names.extend(name for name in request.fields if name not in names)
    return [name for name in names if name not in request.exclude_fields and name != "id"]


def _item_size(item: SearchItem) -> int:
    """結果の文字数に数える項目の長さ。"""
    return (
        len(item.id)
        + sum(len(str(value)) for value in item.values.values())
        + sum(len(snippet) for snippet in item.snippets)
    )


def search_docs(
    request: SearchRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    checker: DocumentChecker,
    seen: SeenStore,
    today: date | None = None,
) -> SearchResult:
    """`search_docs` の要求を処理して検索の結果を返す。"""
    today = today or date.today()  # noqa: DTZ011
    notes: list[str] = []
    targets = resolve_read_targets(
        registry=registry,
        source=request.source,
        ref=request.ref,
        worktree=request.worktree,
        cwd=request.cwd,
    )
    loaded: list[tuple[int, Target, list[Document]]] = []
    schemas: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        result = store.load(target)
        notes.extend(
            f"{problem.path} を読めないので除きました（{problem.detail}）"
            for problem in result.problems
        )
        loaded.append((index, target, result.documents))
        schemas.extend(
            store.schema(target, table.id)
            for table in target.source.config.documents
            if table.enabled and table.type == "yaml"
        )
    fields = known_fields(schemas)
    violations = check_filter(request, fields)
    if violations:
        raise _invalid(violations)
    if request.limit < 1:
        raise _invalid([Violation(path="limit", rule="1 以上にしてください")])
    limit = request.limit
    if limit > LIMIT_MAX:
        limit = LIMIT_MAX
        notes.append(f"limit {request.limit} は上限 {LIMIT_MAX} に丸めました")
    max_chars = request.max_chars
    if max_chars > MAX_CHARS_LIMIT:
        max_chars = MAX_CHARS_LIMIT
        notes.append(f"max_chars {request.max_chars} は上限 {MAX_CHARS_LIMIT} に丸めました")
    hits = [
        _Hit(target, document, index)
        for index, target, documents in loaded
        for document in documents
        if match_filter(request.filter, document, fields=fields, today=today)
    ]
    multi = len(targets) >= MULTI_SOURCE_MIN
    source_label = ",".join(target.source.id for target in targets)
    per_source: dict[str, int] = {}
    if multi:
        per_source = {target.source.id: 0 for target in targets}
        for hit in hits:
            per_source[hit.target.source.id] += 1
        per_source = {name: count for name, count in per_source.items() if count}
    groups = _groups(hits, request.group_by) if request.group_by else []
    if request.view == "count":
        return SearchResult(
            total_count=len(hits),
            returned=0,
            view=request.view,
            per_source=per_source,
            notes=notes,
            groups=groups,
            source_label=source_label,
        )
    ordered = _id_ordered(_order(hits, request), request)
    fingerprint = value_hash(request.model_dump(mode="json", exclude=FINGERPRINT_EXCLUDED))
    base = request.skip + (decode_cursor(request.cursor, fingerprint) if request.cursor else 0)
    window = ordered[base : base + limit]
    key = SessionKey.of(request.session_id, request.agent_id)
    field_chars = request.max_chars_per_field or (
        FIELD_CHARS_FULL if request.view == "full" else FIELD_CHARS_DEFAULT
    )
    words = _leaf_words(request.filter)
    returns_body = request.view == "full" or BODY in request.fields
    seen_ids: dict[str, set[str]] = {}
    if returns_body and not request.repeat_seen and request.snippets is None:
        for target in targets:
            versions = {
                hit.document.id: hit.document.version
                for hit in window
                if hit.target.source.id == target.source.id
            }
            seen_ids[target.source.id] = seen.returned(key, target.source.id, "body", versions)
    items: list[SearchItem] = []
    size = 0
    used: list[_Hit] = []
    returned_bodies: list[_Hit] = []
    truncated = False
    for hit in window:
        document = hit.document
        values: dict[str, Any] = {}
        snippets: list[str] = []
        for name in _field_names(request, document):
            if name == BODY:
                if request.snippets is not None:
                    snippets = snippet_lines(
                        document.body,
                        words,
                        context_lines=request.snippets.context_lines,
                        max_count=request.snippets.max_per_doc,
                    )
                    continue
                if document.id in seen_ids.get(hit.target.source.id, set()):
                    values[name] = SEEN_MARK
                    continue
                values[name] = _cut(document.body, field_chars)
                continue
            values[name] = _cut(_field_value(document, name), field_chars)
        item = SearchItem(
            id=document.id,
            source=hit.target.source.id if multi else None,
            values=values,
            snippets=snippets,
        )
        item_size = _item_size(item)
        if items and size + item_size > max_chars:
            truncated = True
            break
        items.append(item)
        used.append(hit)
        size += item_size
        if BODY in values and values[BODY] != SEEN_MARK:
            returned_bodies.append(hit)
    for hit in used:
        for violation in checker.check(hit.target, hit.document, on="read"):
            notes.append(f"{hit.document.id}: {violation.rule}（{violation.path}）")
    next_cursor: str | None = None
    next_position = base + len(items)
    if next_position < len(ordered) and (
        truncated or len(window) == limit or len(items) < len(window)
    ):
        next_cursor = encode_cursor(next_position - request.skip, fingerprint)
    if truncated:
        notes.append(
            f"max_chars {max_chars} で打ち切りました。cursor を渡して続きを取るか、"
            "fields を絞るか view: ids で取り直してください"
        )
    for target in targets:
        documents = [
            hit.document for hit in returned_bodies if hit.target.source.id == target.source.id
        ]
        seen.mark_returned(key, target.source.id, "body", documents)
    return SearchResult(
        total_count=len(hits),
        returned=len(items),
        view=request.view,
        per_source=per_source,
        next_cursor=next_cursor,
        truncated=truncated,
        notes=notes,
        groups=groups,
        items=items,
        source_label=source_label,
    )
