"""画面の検索。"""

from __future__ import annotations

from collections.abc import Sequence

from dev_docs.features.documents.types import Document
from dev_docs.features.search.filters import match_words, normalize
from dev_docs.features.search.snippets import snippet_lines
from dev_docs.features.view.paths import page_path
from dev_docs.features.view.types import ScreenSearchItem, ScreenSearchResult

SEARCH_QUERY_MAX = 200
SEARCH_LIMIT_DEFAULT = 20
SEARCH_LIMIT_MAX = 100
SNIPPETS_PER_DOC = 3
CONTEXT_LINES = 1


def screen_search(documents: Sequence[Document], q: str, limit: int) -> ScreenSearchResult:
    """語を全て含む文書と一致した箇所を返す。"""
    words = normalize(q).split()
    matched = sorted(
        (document for document in documents if match_words(document, words)), key=page_path
    )
    items = [
        ScreenSearchItem(
            path=page_path(document),
            name=str(document.metadata["name"]),
            snippets=snippet_lines(
                document.body, words, context_lines=CONTEXT_LINES, max_count=SNIPPETS_PER_DOC
            ),
        )
        for document in matched[:limit]
    ]
    return ScreenSearchResult(total_count=len(matched), items=items)
