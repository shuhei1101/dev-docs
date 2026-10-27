from __future__ import annotations

from dev_docs.features.search.render import render_search_markdown
from dev_docs.features.search.types import SearchItem, SearchResult


def test_render_search_markdown() -> None:
    """一覧の表（正常系）。"""
    # 準備
    items = [
        SearchItem(
            id=f"doc-{number}",
            source=None,
            values={
                "kind": "sample",
                "name": f"文書 {number}",
                "description": f"{number} 件目",
                "@chars": 320,
                "version": "9d0e11",
            },
        )
        for number in (1, 2)
    ]
    result = SearchResult(total_count=2, returned=2, view="summary", items=items)
    # 実行
    markdown = render_search_markdown(result, source_label="sample")
    # 検証
    assert markdown.splitlines()[0] == "sample: 該当 2 件・返した 2 件"
    assert "| id | kind | name | description | chars | version |" in markdown
