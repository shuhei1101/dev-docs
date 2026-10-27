from __future__ import annotations

from pathlib import Path

from dev_docs.features.access.types import SourceAccess, Workplace
from dev_docs.features.describe.render import render_describe_markdown
from dev_docs.features.describe.types import SourceListResult


def test_render_describe_markdown() -> None:
    """一覧の表（正常系）。"""
    # 準備
    result = SourceListResult(
        workplace=Workplace(cwd=Path("/w/sample"), source_id="sample", worktree=None),
        sources=[
            SourceAccess(source_id="sample", access="write", current=True, description="サンプル"),
            SourceAccess(source_id="notes", access="read", current=False, description="メモ"),
        ],
    )
    # 実行
    markdown = render_describe_markdown(result)
    # 検証
    assert "| sample | write（作業中） | サンプル |" in markdown
    assert "| notes | read | メモ |" in markdown
