"""画面の検索。"""

from __future__ import annotations

from collections.abc import Sequence

from dev_docs.features.documents.types import Document
from dev_docs.features.view.types import ScreenSearchResult

SEARCH_QUERY_MAX = 200
SEARCH_LIMIT_DEFAULT = 20
SEARCH_LIMIT_MAX = 100
SNIPPETS_PER_DOC = 3


def screen_search(documents: Sequence[Document], q: str, limit: int) -> ScreenSearchResult:
    """語を全て含む文書と一致した箇所を返す。"""
    raise NotImplementedError
