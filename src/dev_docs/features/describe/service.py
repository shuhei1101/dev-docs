"""`describe` の処理。"""

from __future__ import annotations

import dataclasses

from dev_docs.features.access.service import (
    available_sources,
    describe_workplace,
    resolve_read_targets,
)
from dev_docs.features.describe.types import (
    DescribeRequest,
    KindSchemaResult,
    KindSummary,
    SourceGuideResult,
    SourceListResult,
)
from dev_docs.features.documents.store import DocumentStore
from dev_docs.features.sources.registry import SourceRegistry
from dev_docs.features.sources.service import load_source_at
from dev_docs.shared.errors import InvalidArgumentError, Violation


def describe(
    request: DescribeRequest, *, registry: SourceRegistry, store: DocumentStore
) -> SourceListResult | SourceGuideResult | KindSchemaResult:
    """`describe` の要求を処理して結果を返す。"""
    if request.source is None:
        if request.kind is not None:
            raise InvalidArgumentError(
                message="kind には source が要ります",
                violations=[
                    Violation(
                        path="kind",
                        rule="kind には source が要ります",
                        fix="source も渡してください",
                    )
                ],
            )
        return SourceListResult(
            workplace=describe_workplace(request.cwd, registry=registry),
            sources=available_sources(request.cwd, registry=registry),
        )
    target = resolve_read_targets(
        registry=registry, source=request.source, worktree=request.worktree, cwd=request.cwd
    )[0]
    # 作業ツリーかワークツリーを読むときは、その場所の設定を読み直した配信元を使う
    if target.worktree is not None and target.ref is None:
        target = dataclasses.replace(target, source=load_source_at(target.source, target.worktree))
    source = target.source
    if request.kind is None:
        kinds = []
        for table in source.config.documents:
            if not table.enabled:
                continue
            schema = store.schema(target, table.id)
            kinds.append(
                KindSummary(
                    id=table.id, description=str(schema.get("description") or table.title or "")
                )
            )
        return SourceGuideResult(
            source_id=source.id, instructions=source.config.instructions, kinds=kinds
        )
    table = source.table(request.kind)
    schema = store.schema(target, table.id)
    schema_text = ""
    schema_file = store.read_root(target) / table.schema_path
    if schema_file.is_file():
        schema_text = schema_file.read_text(encoding="utf-8")
    return KindSchemaResult(
        source_id=source.id,
        kind=table.id,
        schema_text=schema_text,
        schema=schema,
        metadata=dict(table.metadata),
    )
