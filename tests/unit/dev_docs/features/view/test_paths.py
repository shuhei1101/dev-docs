from __future__ import annotations

from collections.abc import Callable

from dev_docs.features.view.paths import find_page, page_path
from dev_docs.integrations.project_index.types import IndexedDocument as Document


def test_page_path(make_document: Callable[..., Document]) -> None:
    """ファイルと records（正常系）。"""
    # 準備
    plain = make_document(id="a", path="docs/a.yaml")
    record = make_document(id="r-1", path="docs/rules.yaml", record_index=0)
    # 実行
    plain_result = page_path(plain)
    record_result = page_path(record)
    # 検証
    assert plain_result == "docs/a"
    assert record_result == "docs/rules/r-1"


def test_find_page(make_document: Callable[..., Document]) -> None:
    """文書のページのパスで該当する（正常系）。"""
    # 準備
    document = make_document(id="a", path="rules/a.yaml")
    other = make_document(id="b", path="rules/b.yaml")
    # 実行
    result = find_page([other, document], "rules/a")
    # 検証
    assert result is document


def test_find_page_when_body_path(make_document: Callable[..., Document]) -> None:
    """本文のファイルのパスで該当する（正常系）。"""
    # 準備
    plain = make_document(id="a", path="rules/a.yaml")
    record = make_document(
        id="notes/b", path="notes/files.yaml", record_index=0, body_path="notes/b.md"
    )
    # 実行
    result = find_page([plain, record], "notes/b.md")
    # 検証
    assert result is record


def test_find_page_when_missing(make_document: Callable[..., Document]) -> None:
    """どれにも該当しない（正常系）。"""
    # 準備
    plain = make_document(id="a", path="rules/a.yaml")
    record = make_document(
        id="notes/b", path="notes/files.yaml", record_index=0, body_path="notes/b.md"
    )
    # 実行
    result = find_page([plain, record], "no/such")
    # 検証
    assert result is None
