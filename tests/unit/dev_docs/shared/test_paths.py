from __future__ import annotations

from pathlib import Path

from dev_docs.shared.paths import normalize_path


def test_normalize_path() -> None:
    """`..` と末尾の `/` を除く（正常系）。"""
    # 実行
    result = normalize_path("/r/a/../b/")
    # 検証
    assert result == Path("/r/b")
