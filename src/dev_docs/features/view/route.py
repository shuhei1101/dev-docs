"""文書の画面と画面の API のルート。"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response

from dev_docs.features.history.query import list_refs
from dev_docs.features.view.columns import ColumnSettings
from dev_docs.features.view.page import render_doc_view, render_error_page
from dev_docs.features.view.paths import screen_path_of, screen_target
from dev_docs.features.view.search import (
    SEARCH_LIMIT_DEFAULT,
    SEARCH_LIMIT_MAX,
    SEARCH_QUERY_MAX,
    screen_search,
)
from dev_docs.features.view.types import ColumnsRequest, ScreenSearchResult
from dev_docs.server.origin import require_same_origin
from dev_docs.shared.errors import DevDocsError

if TYPE_CHECKING:
    from dev_docs.main import Handlers

REFS_COMMITS_DEFAULT = 20
REFS_COMMITS_MAX = 100


def _wants_html(request: Request) -> bool:
    """画面の GET か（`Accept` に `text/html` を含む）を返す。"""
    return "text/html" in request.headers.get("accept", "")


def build_view_router(handlers: Handlers) -> APIRouter:
    """文書の画面と画面の API のルートを持つルーターを作る。"""
    router = APIRouter()

    @router.get("/_api/sources/{source}/search")
    async def search(
        source: str,
        q: Annotated[str, Query(min_length=1, max_length=SEARCH_QUERY_MAX)],
        ref: str | None = None,
        limit: Annotated[int, Query(ge=1, le=SEARCH_LIMIT_MAX)] = SEARCH_LIMIT_DEFAULT,
    ) -> ScreenSearchResult:
        def work() -> ScreenSearchResult:
            target, _ = screen_target(source, ref, registry=handlers.registry)
            documents = [
                document
                for document in handlers.store.load(target).documents
                if target.source.table(document.kind).search
            ]
            return screen_search(documents, q, limit)

        return await asyncio.to_thread(work)

    @router.get("/_api/sources/{source}/refs")
    async def refs(
        source: str,
        commits: Annotated[int, Query(ge=0, le=REFS_COMMITS_MAX)] = REFS_COMMITS_DEFAULT,
    ) -> dict[str, Any]:
        served = handlers.registry.get(source)
        result = await asyncio.to_thread(list_refs, served, commits=commits)
        return dataclasses.asdict(result)

    @router.put("/_api/sources/{source}/columns", dependencies=[Depends(require_same_origin)])
    async def columns(source: str, body: ColumnsRequest) -> ColumnsRequest:
        handlers.registry.get(source)
        settings: ColumnSettings = handlers.columns
        await asyncio.to_thread(settings.save, source, body.table, body.hidden)
        return body

    async def page(request: Request) -> Response:
        screen = screen_path_of(request)
        diff_ref = request.query_params.get("diff")
        try:
            return await asyncio.to_thread(
                render_doc_view, request, screen, handlers=handlers, diff_ref=diff_ref
            )
        except DevDocsError as error:
            if _wants_html(request):
                return render_error_page(request, error, handlers=handlers)
            raise

    @router.get("/{source_part}", response_class=HTMLResponse)
    async def source_top(request: Request, source_part: str) -> Response:
        return await page(request)

    @router.get("/{source_part}/{page_path:path}", response_class=HTMLResponse)
    async def source_page(request: Request, source_part: str, page_path: str) -> Response:
        return await page(request)

    return router
