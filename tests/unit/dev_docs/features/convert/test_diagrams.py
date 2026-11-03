from __future__ import annotations

import json
import re
from typing import Any

import pytest

from dev_docs.features.convert.diagrams import render_diagram, render_mermaid
from dev_docs.features.convert.types import DiagramHead

HEAD = DiagramHead(title="図", scope="文書", updated="2026-11-03")


def _definition(block: str, marker: str) -> dict[str, Any]:
    """部品の範囲から定義の JSON を取り出す。"""
    match = re.search(
        rf"<!-- {marker} -->\n\n```json\n(.*?)\n```\n\n<!-- /{marker} -->", block, re.S
    )
    assert match is not None, block
    definition: dict[str, Any] = json.loads(match.group(1))
    return definition


def test_render_diagram() -> None:
    """フローチャート（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "label": "x"}],
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    definition = _definition(result, "flow")
    assert (definition["title"], definition["scope"], definition["updated"]) == (
        "図",
        "文書",
        "2026-11-03",
    )
    assert [node["name"] for node in definition["nodes"]] == ["A", "B"]
    assert [wire["label"] for wire in definition["wires"]] == ["x"]
    assert "```mermaid" not in result


def test_render_diagram_when_node_kinds() -> None:
    """箱の種類（正常系）。"""
    # 準備
    value = {
        "nodes": [
            {"id": "a", "kind": "actor"},
            {"id": "b", "kind": "store"},
            {"id": "c", "kind": "process"},
        ],
        "edges": [],
    }
    # 実行
    result = render_diagram(value, "dataflow", HEAD)
    # 検証
    assert [node["kind"] for node in _definition(result, "flow")["nodes"]] == [
        "external",
        "data",
        "script",
    ]


def test_render_diagram_when_state() -> None:
    """状態遷移（正常系）。"""
    # 準備
    value = {
        "initial": "下書き",
        "final": ["公開"],
        "states": [{"name": "下書き"}, {"name": "公開"}],
        "transitions": [
            {"from": "下書き", "to": "公開", "trigger": "公開する", "condition": "承認済み"},
            {"from": "公開", "to": "下書き", "trigger": "取り下げる"},
        ],
    }
    # 実行
    result = render_diagram(value, "state", HEAD)
    # 検証
    definition = _definition(result, "flow")
    subs = {node["name"]: node.get("sub") for node in definition["nodes"]}
    assert subs == {"下書き": "初期状態", "公開": "終了状態"}
    assert definition["wires"][0]["label"] == "公開する [承認済み]"


def test_render_diagram_when_er() -> None:
    """ER 図は Mermaid のまま（正常系）。"""
    # 準備
    value = {"entities": [{"name": "users", "columns": [{"name": "id", "type": "int"}]}]}
    # 実行
    result = render_diagram(value, "er", HEAD)
    # 検証
    assert result.startswith("```mermaid\nerDiagram")


def test_render_diagram_when_unknown() -> None:
    """知らない種類（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match="gantt"):
        render_diagram({}, "gantt", HEAD)  # type: ignore[arg-type]


def test_render_mermaid() -> None:
    """シーケンス図（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  participant A as 画面\n  A->>B: 読む"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    definition = _definition(result, "sequence")
    assert [p["name"] for p in definition["participants"]] == ["画面", "B"]
    assert [step["label"] for step in definition["steps"]] == ["読む"]


def test_render_mermaid_when_flowchart() -> None:
    """フローチャート（正常系）。"""
    # 実行
    result = render_mermaid("flowchart TD\n  a --> b", HEAD)
    # 検証
    assert len(_definition(result, "flow")["nodes"]) == 2


def test_render_mermaid_when_unreadable() -> None:
    """読み取れないコード（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  A->>B: 読む\n  Note over A: 補足"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    assert result == f"```mermaid\n{code}\n```"
