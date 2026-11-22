"""メタデータの取得と編集中の変更の直コミットのルート。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from dev_docs.features.metadata.commits import CommitRequest, CommitResult, commit_edits
from dev_docs.features.metadata.metadata import MetadataResponse, build_metadata
from dev_docs.server.origin import require_same_origin

if TYPE_CHECKING:
    from dev_docs.main import Handlers

__all__ = ["build_metadata_router"]


def build_metadata_router(handlers: Handlers) -> APIRouter:
    """メタデータの 2 つのルートを持つ `APIRouter` を作る。"""
    router = APIRouter(tags=["metadata"])

    @router.get("/_api/sources/{source}/metadata", name="get_metadata")
    async def get_metadata(source: str) -> MetadataResponse:
        # 配信元が無い（404）・つながらない（503）は例外の変換の登録に任せる
        return await build_metadata(handlers.project_index, source)

    @router.post(
        "/_api/sources/{source}/commits",
        name="post_commits",
        dependencies=[Depends(require_same_origin)],
    )
    async def post_commits(source: str, body: CommitRequest) -> CommitResult:
        return await commit_edits(handlers.project_index, source, body)

    return router
