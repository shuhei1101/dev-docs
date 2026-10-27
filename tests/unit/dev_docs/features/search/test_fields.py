from __future__ import annotations

from collections.abc import Callable

from dev_docs.features.documents.types import Document
from dev_docs.features.search.fields import field_values


def test_field_values(make_document: Callable[..., Document]) -> None:
    """項目の種類ごとの値（正常系）。"""
    # 準備
    document = make_document(
        metadata={"tags": ["a", "b"]},
        data={"owner": {"name": "x"}},
        body="# 見出し",
    )
    # 実行
    tags = field_values(document, "tags")
    owner = field_values(document, "owner.name")
    chars = field_values(document, "@chars")
    missing = field_values(document, "missing")
    # 検証
    assert tags == ["a", "b"]
    assert owner == ["x"]
    assert chars == [5]
    assert missing == []
