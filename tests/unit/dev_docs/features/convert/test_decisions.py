from __future__ import annotations

import pytest

from dev_docs.features.convert.decisions import decision_page_id


def test_decision_page_id() -> None:
    """検討事項の文書のパス（正常系）。"""
    # 実行
    result = decision_page_id("_decisions/D-1")
    # 検証
    assert result == "D-1"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("dev/a", id="other"),
        pytest.param("_decisions/../x", id="outside"),
        pytest.param("_decisions/d-1", id="lowercase"),
    ],
)
def test_decision_page_id_when_other(path: str) -> None:
    """検討事項の文書でないパスと、形式に合わない ID（正常系）。"""
    # 実行
    result = decision_page_id(path)
    # 検証
    assert result is None
