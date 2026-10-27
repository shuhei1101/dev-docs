from __future__ import annotations

from collections.abc import Callable

from dev_docs.features.documents.types import Document
from dev_docs.features.view.search import screen_search


def test_screen_search(make_document: Callable[..., Document]) -> None:
    """全ての語を含む文書だけ（正常系）。"""
    # 準備
    both = make_document(
        id="both", path="docs/both.yaml", body="先頭の行\nfoo の説明\nbar の説明\n"
    )
    only_foo = make_document(id="only-foo", path="docs/only-foo.yaml", body="foo だけ\n")
    # 実行
    result = screen_search([both, only_foo], "foo bar", 20)
    # 検証
    assert result.total_count == 1
    assert result.items[0].path == "docs/both"
    assert any("foo" in line or "bar" in line for line in result.items[0].snippets)
