"""関連のたどりの結果の Markdown。"""

from __future__ import annotations

from dev_docs.features.related.types import RelatedResult


def render_related_markdown(result: RelatedResult) -> str:
    """`format: markdown` の本文を作る。"""
    raise NotImplementedError
