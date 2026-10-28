from __future__ import annotations

from dev_docs.features.search.render import render_search_markdown
from dev_docs.features.search.types import SearchItem, SearchResult, Snippet, SnippetLine


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


def test_render_search_markdown_when_full() -> None:
    """場所と範囲を属性にする（正常系）。"""
    # 準備
    items = [
        SearchItem(
            id="doc-1",
            source=None,
            values={"body": "id: doc-1\n"},
            path="/ws/docs/doc-1.yaml",
            scope="full",
        ),
        SearchItem(id="doc-2", source=None, values={"body": "id: doc-2\n"}),
    ]
    result = SearchResult(total_count=2, returned=2, view="full", items=items)
    # 実行
    markdown = render_search_markdown(result, source_label="sample")
    # 検証
    lines = markdown.splitlines()
    assert lines.count('<document path="/ws/docs/doc-1.yaml" scope="full">') == 1
    assert lines.count("<document>") == 1
    assert lines.count("</document>") == 2


def test_render_search_markdown_when_snippets() -> None:
    """抜粋の書式（正常系）。"""
    # 準備
    snippets = [
        Snippet(
            lines=[
                SnippetLine(line=3, text="## a", hit=True),
                SnippetLine(line=4, text="b", hit=False),
            ]
        ),
        Snippet(lines=[SnippetLine(line=9, text="## c", hit=True)]),
    ]
    items = [SearchItem(id="doc-1", source=None, values={}, snippets=snippets)]
    result = SearchResult(total_count=1, returned=1, view="full", items=items)
    # 実行
    markdown = render_search_markdown(result, source_label="sample")
    # 検証
    lines = markdown.splitlines()
    first = lines.index("3:## a")
    assert lines[first : first + 4] == ["3:## a", "4-b", "--", "9:## c"]
    assert lines.index("<document>") < first
    assert first + 3 < lines.index("</document>")
