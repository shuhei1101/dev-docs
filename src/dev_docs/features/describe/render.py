"""説明の Markdown。"""

from __future__ import annotations

from dev_docs.features.describe.types import KindSchemaResult, SourceGuideResult, SourceListResult


def render_describe_markdown(
    result: SourceListResult | SourceGuideResult | KindSchemaResult,
) -> str:
    """`format: markdown` の本文を作る。"""
    raise NotImplementedError
