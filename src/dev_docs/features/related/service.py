"""`trace_related` の処理。"""

from __future__ import annotations

import posixpath

from dev_docs.features.access.service import resolve_read_targets
from dev_docs.features.access.types import Target
from dev_docs.features.documents.store import DocumentStore, not_found_error
from dev_docs.features.documents.types import Document
from dev_docs.features.history.query import co_changed_files
from dev_docs.features.related.graph import walk_related
from dev_docs.features.related.suggest import suggest_related
from dev_docs.features.related.types import (
    DEPTH_MAX,
    RelatedItem,
    RelatedRequest,
    RelatedResult,
)
from dev_docs.features.seen.store import SeenStore
from dev_docs.features.seen.types import SEEN_MARK, SessionKey
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.integrations.git import GitError
from dev_docs.shared.errors import (
    DevDocsError,
    DocumentNotFoundError,
    InvalidArgumentError,
    Violation,
)


def _invalid(rule: str, path: str) -> InvalidArgumentError:
    """引数の違反 1 件の `InvalidArgumentError` を作る。"""
    return InvalidArgumentError(
        message=rule, violations=[Violation(path=path, rule=rule, fix=rule)]
    )


def _co_changed(target: Target, start: list[Document]) -> dict[str, int]:
    """起点のファイルと一緒に変わったファイルを、配信元の直下からのパスで返す（Git だけ）。"""
    source = target.source
    if not source.is_git or source.repo_root is None:
        return {}
    prefix = source.root.relative_to(source.repo_root).as_posix()
    paths = {document.body_path or document.path for document in start}
    repo_paths = [path if prefix == "." else f"{prefix}/{path}" for path in sorted(paths)]
    try:
        counts = co_changed_files(target.worktree or source.repo_root, repo_paths)
    except GitError:
        return {}
    if prefix == ".":
        return counts
    return {
        path.removeprefix(f"{prefix}/"): count
        for path, count in counts.items()
        if path.startswith(f"{prefix}/")
    }


def trace_related(
    request: RelatedRequest,
    *,
    registry: SourceRegistry,
    store: DocumentStore,
    seen: SeenStore,
) -> RelatedResult:
    """`trace_related` の要求を処理して関連のたどりの結果を返す。"""
    if (request.from_ids is None) == (request.code_paths is None):
        raise _invalid("from_ids か code_paths のどちらか 1 つを渡してください", "from_ids")
    if request.depth < 1:
        raise _invalid("depth は 1 以上にしてください", "depth")
    notes: list[str] = []
    depth = request.depth
    if depth > DEPTH_MAX:
        depth = DEPTH_MAX
        notes.append(f"depth {request.depth} は上限 {DEPTH_MAX} に丸めました")
    target = resolve_read_targets(
        registry=registry,
        source=request.source,
        ref=request.ref,
        worktree=request.worktree,
        cwd=request.cwd,
    )[0]
    documents = {document.id: document for document in store.load(target).documents}
    if request.from_ids is not None:
        missing = [doc_id for doc_id in request.from_ids if doc_id not in documents]
        if missing:
            raise not_found_error(target.source.id, missing, list(documents))
        start = [documents[doc_id] for doc_id in request.from_ids]
    else:
        wanted = [posixpath.normpath(path).removeprefix("./") for path in request.code_paths or []]
        by_path = {document.body_path or document.path: document for document in documents.values()}
        missing = [path for path in wanted if path not in by_path]
        if missing:
            raise DocumentNotFoundError(
                message=f"文書がありません: {', '.join(missing)}",
                missing=missing,
                next_steps=["search_docs で body_path を確かめてください"],
            )
        start = [by_path[path] for path in wanted]
    other_cache: dict[str, dict[str, Document]] = {}
    other_targets: dict[str, Target] = {}

    def resolve_other(source_id: str, doc_id: str) -> Document | None:
        """別の配信元の文書を、同じ作業場所の権限で引く。"""
        if source_id not in other_cache:
            try:
                other = resolve_read_targets(registry=registry, source=source_id, cwd=request.cwd)[
                    0
                ]
                other_cache[source_id] = {d.id: d for d in store.load(other).documents}
                other_targets[source_id] = other
            except DevDocsError:
                other_cache[source_id] = {}
        return other_cache[source_id].get(doc_id)

    found, walk_notes = walk_related(
        start, documents, depth=depth, direction=request.direction, resolve_other=resolve_other
    )
    notes.extend(walk_notes)
    key = SessionKey.of(request.session_id, request.agent_id)
    seen_ids: dict[str, set[str]] = {}
    if not request.repeat_seen:
        for source_id in {document.source_id for document, *_ in found}:
            versions = {d.id: d.version for d, *_ in found if d.source_id == source_id}
            seen_ids[source_id] = seen.returned(key, source_id, "related", versions)

    def _location(document: Document) -> str | None:
        """たどった文書を読んだ場所での絶対パスを返す（`ref` を渡した呼び出しは `None`）。"""
        if request.ref is not None:
            return None
        read_target = (
            target
            if document.source_id == target.source.id
            else other_targets.get(document.source_id)
        )
        return store.location(read_target, document) if read_target is not None else None

    items: list[RelatedItem] = []
    returned: dict[str, list[Document]] = {}
    for document, level, via_from, via_type, via_direction in found:
        already = document.id in seen_ids.get(document.source_id, set())
        name = str(document.metadata.get("name", ""))
        description = str(document.metadata.get("description", ""))
        path = None if already else _location(document)
        items.append(
            RelatedItem(
                id=document.id,
                source=document.source_id if document.source_id != target.source.id else None,
                depth=level,
                via_from=via_from,
                via_type=via_type,
                via_direction=via_direction,
                name=SEEN_MARK if already else name,
                description=SEEN_MARK if already else description,
                path=path,
                scope="summary" if path else None,
            )
        )
        if not already:
            returned.setdefault(document.source_id, []).append(document)
    suggestions = []
    if request.suggest:
        exclude = {document.id for document in start} | {document.id for document, *_ in found}
        suggestions = suggest_related(
            start,
            list(documents.values()),
            exclude=exclude,
            co_changed=_co_changed(target, start),
            activity=seen.activity(key, target.source.id),
        )
    for source_id, docs in returned.items():
        seen.mark_returned(key, source_id, "related", docs)
    return RelatedResult(
        start=[document.id for document in start],
        items=items,
        suggestions=suggestions,
        notes=notes,
    )
