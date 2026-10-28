from __future__ import annotations

import pytest

from dev_docs.features.convert.diagrams import render_diagram


def test_render_diagram() -> None:
    """フローチャート（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "label": "x"}],
    }
    # 実行
    result = render_diagram(value, "flowchart")
    # 検証
    assert "flowchart TD" in result
    assert "a[A]" in result
    assert "a -->|x| b" in result


def test_render_diagram_when_state() -> None:
    """状態遷移（正常系）。"""
    # 準備
    value = {
        "initial": "下書き",
        "states": [{"name": "下書き"}, {"name": "公開"}],
        "transitions": [
            {"from": "下書き", "to": "公開", "trigger": "公開する"},
            {"from": "公開", "to": "下書き", "trigger": "取り下げる"},
        ],
    }
    # 実行
    result = render_diagram(value, "state")
    # 検証
    assert "stateDiagram-v2" in result
    assert "[*] --> 下書き" in result
    assert "下書き --> 公開 : 公開する" in result


def test_render_diagram_when_unknown() -> None:
    """知らない種類（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match="gantt"):
        render_diagram({}, "gantt")  # type: ignore[arg-type]
