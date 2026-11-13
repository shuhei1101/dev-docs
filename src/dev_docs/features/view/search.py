"""画面の検索（project-index の検索の結果を画面の構造にする）。"""

from __future__ import annotations

from pathlib import PurePosixPath

from dev_docs.features.view.paths import page_path
from dev_docs.features.view.types import ScreenSearchItem, ScreenSearchResult
from dev_docs.integrations.project_index.client import ProjectIndexClient
from dev_docs.integrations.project_index.types import SearchHit

SEARCH_QUERY_MAX = 200
SEARCH_LIMIT_DEFAULT = 20
SEARCH_LIMIT_MAX = 100


async def screen_search(
    client: ProjectIndexClient, source_id: str, q: str, *, ref: str | None, limit: int
) -> ScreenSearchResult:
    """project-index の検索の結果を、文書のページのパスの画面の検索の結果にする。"""
    hits = await client.search(source_id, q, ref=ref, limit=limit)
    view = await client.source_view(source_id)
    listed = await client.list_documents(
        source_id, ref=ref, record_kinds=view.record_kinds(), values=False
    )
    by_key = {(document.path, document.id): document for document in listed.documents}

    def _page(hit: SearchHit) -> str:
        found = by_key.get((hit.path, hit.id))
        if found is not None:
            return page_path(found)
        return PurePosixPath(hit.path).with_suffix("").as_posix()

    items = [
        ScreenSearchItem(path=_page(hit), name=hit.name, snippets=list(hit.snippets))
        for hit in hits.items
    ]
    return ScreenSearchResult(total_count=hits.total_count, items=items)
