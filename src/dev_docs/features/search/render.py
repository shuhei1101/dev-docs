"""検索の結果の Markdown。"""

from __future__ import annotations

from dev_docs.features.search.types import SearchResult


def render_search_markdown(result: SearchResult, *, source_label: str) -> str:
    """`format: markdown` の本文を作る。"""
    raise NotImplementedError
