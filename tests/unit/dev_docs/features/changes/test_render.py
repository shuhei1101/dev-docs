from __future__ import annotations

from datetime import UTC, datetime

from dev_docs.features.changes.render import render_changes_markdown
from dev_docs.features.changes.types import ChangeItem, ChangesResult, RangePoint


def test_render_changes_markdown() -> None:
    """区間と表（正常系）。"""
    # 準備
    result = ChangesResult(
        range_from=RangePoint(
            input="3f2a9c1", commit="3f2a9c1", date=datetime(2026, 10, 26, 10, 0, tzinfo=UTC)
        ),
        range_to=RangePoint(
            input="8b1d4e0", commit="8b1d4e0", date=datetime(2026, 10, 26, 11, 30, tzinfo=UTC)
        ),
        total_count=1,
        items=[
            ChangeItem(
                id="doc-1",
                source=None,
                change="modified",
                keys=["name"],
                values={"name": ("文書 1", "新しい名前")},
            )
        ],
    )
    # 実行
    markdown = render_changes_markdown(result, source_label="sample")
    # 検証
    first_line = markdown.splitlines()[0]
    assert first_line.startswith("sample: 3f2a9c1（")
    assert "→ 8b1d4e0（" in first_line
    assert first_line.endswith("・変わった文書 1 件")
    assert "| doc-1 | modified | name |" in markdown
