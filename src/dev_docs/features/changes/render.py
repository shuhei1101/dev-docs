"""変更の結果の Markdown。"""

from __future__ import annotations

from dev_docs.features.changes.types import ChangesResult


def render_changes_markdown(result: ChangesResult, *, source_label: str) -> str:
    """`format: markdown` の本文を作る。"""
    raise NotImplementedError
