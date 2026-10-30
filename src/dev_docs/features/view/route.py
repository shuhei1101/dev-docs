"""画面の API のルート。"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from dev_docs.features.history.query import list_refs
from dev_docs.features.view.columns import ColumnSettings
from dev_docs.features.view.document import get_document, not_found_fields
from dev_docs.features.view.paths import screen_target
from dev_docs.features.view.search import (
    SEARCH_LIMIT_DEFAULT,
    SEARCH_LIMIT_MAX,
    SEARCH_QUERY_MAX,
    screen_search,
)
from dev_docs.features.view.types import (
    ColumnsRequest,
    DocumentResponse,
    RefsResponse,
    ScreenSearchResult,
)
from dev_docs.server.error_handlers import problem_of
from dev_docs.server.origin import require_same_origin
from dev_docs.shared.errors import DevDocsError

if TYPE_CHECKING:
    from dev_docs.main import Handlers

REFS_COMMITS_DEFAULT = 20
REFS_COMMITS_MAX = 100


def build_view_router(handlers: Handlers) -> APIRouter:
    """画面の API のルートを持つルーターを作る。"""
    router = APIRouter(tags=["view"])

    async def document(
        source: str, path: str | None, ref: str | None, diff: str | None
    ) -> Response | DocumentResponse:
        """文書を取得し、見つからなかったときは何が無いかを足した 404 にする。"""
        try:
            return await asyncio.to_thread(
                get_document, source, path, handlers=handlers, ref=ref, diff_ref=diff
            )
        except DevDocsError as error:
            fields = not_found_fields(error, path, source_id=source)
            if fields is None:
                raise
            return problem_of(error, fields)

    @router.get(
        "/_api/sources/{source}/docs",
        name="get_document_default",
        response_model=DocumentResponse,
    )
    async def get_document_default(
        source: str, ref: str | None = None, diff: str | None = None
    ) -> Response | DocumentResponse:
        return await document(source, None, ref, diff)

    @router.get(
        "/_api/sources/{source}/docs/{path:path}",
        name="get_document",
        response_model=DocumentResponse,
    )
    async def get_document_at(
        source: str, path: str, ref: str | None = None, diff: str | None = None
    ) -> Response | DocumentResponse:
        return await document(source, path, ref, diff)

    @router.get("/_api/sources/{source}/search", name="search_page")
    async def search(
        source: str,
        q: Annotated[str, Query(min_length=1, max_length=SEARCH_QUERY_MAX)],
        ref: str | None = None,
        limit: Annotated[int, Query(ge=1, le=SEARCH_LIMIT_MAX)] = SEARCH_LIMIT_DEFAULT,
    ) -> ScreenSearchResult:
        def work() -> ScreenSearchResult:
            target, _ = screen_target(source, ref, registry=handlers.registry)
            documents = [
                found
                for found in handlers.store.load(target).documents
                if target.source.table(found.kind).search
            ]
            return screen_search(documents, q, limit)

        return await asyncio.to_thread(work)

    @router.get("/_api/sources/{source}/refs", name="list_refs")
    async def refs(
        source: str,
        commits: Annotated[int, Query(ge=0, le=REFS_COMMITS_MAX)] = REFS_COMMITS_DEFAULT,
    ) -> RefsResponse:
        served = handlers.registry.get(source)
        result = await asyncio.to_thread(list_refs, served, commits=commits)
        return RefsResponse.model_validate(dataclasses.asdict(result))

    @router.put(
        "/_api/sources/{source}/columns",
        name="put_columns",
        dependencies=[Depends(require_same_origin)],
    )
    async def columns(source: str, body: ColumnsRequest) -> ColumnsRequest:
        handlers.registry.get(source)
        settings: ColumnSettings = handlers.columns
        await asyncio.to_thread(settings.save, source, body.table, body.hidden)
        return body

    return router
