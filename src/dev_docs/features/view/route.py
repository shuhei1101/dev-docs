"""画面の API のルート。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from dev_docs.features.view.document import get_document, not_found_fields
from dev_docs.features.view.search import (
    SEARCH_LIMIT_DEFAULT,
    SEARCH_LIMIT_MAX,
    SEARCH_QUERY_MAX,
    screen_search,
)
from dev_docs.features.view.types import (
    ColumnsRequest,
    CommitItem,
    DocumentResponse,
    RefItem,
    RefsResponse,
    ScreenSearchResult,
)
from dev_docs.server.error_handlers import problem_of
from dev_docs.server.origin import require_same_origin
from dev_docs.shared.errors import DevDocsError, ProjectIndexUnreachableError

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
            return await get_document(source, path, handlers=handlers, ref=ref, diff_ref=diff)
        except ProjectIndexUnreachableError:
            raise
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
        return await screen_search(handlers.project_index, source, q, ref=ref, limit=limit)

    @router.get("/_api/sources/{source}/refs", name="list_refs")
    async def refs(
        source: str,
        commits: Annotated[int, Query(ge=0, le=REFS_COMMITS_MAX)] = REFS_COMMITS_DEFAULT,
    ) -> RefsResponse:
        result = await handlers.project_index.refs(source, commits=commits)
        return RefsResponse(
            git=result.git,
            default_ref=result.default_ref,
            branches=[RefItem(name=b.name, commit=b.commit) for b in result.branches],
            tags=[RefItem(name=t.name, commit=t.commit) for t in result.tags],
            commits=[
                CommitItem(commit=c.commit, date=c.date.isoformat(), subject=c.subject)
                for c in result.commits
            ],
        )

    @router.put(
        "/_api/sources/{source}/columns",
        name="put_columns",
        dependencies=[Depends(require_same_origin)],
    )
    async def columns(source: str, body: ColumnsRequest) -> ColumnsRequest:
        await handlers.project_index.source_view(source)
        await asyncio.to_thread(handlers.columns.save, source, body.table, body.hidden)
        return body

    return router
