"""画面の検索（project-index の検索の結果を画面の形にする）。"""

from __future__ import annotations

from dev_docs.features.view.paths import page_path
from dev_docs.features.view.types import ScreenSearchItem, ScreenSearchResult
from dev_docs.integrations.project_index.client import ProjectIndexClient

SEARCH_QUERY_MAX = 200
SEARCH_LIMIT_DEFAULT = 20
SEARCH_LIMIT_MAX = 100


async def screen_search(
    client: ProjectIndexClient, source_id: str, q: str, *, ref: str | None, limit: int
) -> ScreenSearchResult:
    """project-index の検索の結果を、文書のページのパスの画面の検索の結果にする。"""
    hits = await client.search(source_id, q, ref=ref, limit=limit)
    items = [
        ScreenSearchItem(path=page_path(hit), name=hit.name, snippets=list(hit.snippets))
        for hit in hits.items
    ]
    return ScreenSearchResult(total_count=hits.total_count, items=items)
