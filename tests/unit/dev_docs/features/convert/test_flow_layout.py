from __future__ import annotations

from typing import Any

from dev_docs.features.convert.flow_layout import layout_flow
from dev_docs.features.convert.types import DiagramHead, FlowEdge, FlowGraph, FlowNode

HEAD = DiagramHead(title="図", scope="文書", updated="2026-11-03")


def _graph(direction: str, edges: list[tuple[str, str, str | None]]) -> FlowGraph:
    """線の端に出た順の箱を持つ中間データを作る。"""
    ids: list[str] = []
    for source, target, _ in edges:
        for node_id in (source, target):
            if node_id not in ids:
                ids.append(node_id)
    return FlowGraph(
        direction=direction,  # type: ignore[arg-type]
        nodes=[FlowNode(id=node_id, name=node_id.upper(), kind="script") for node_id in ids],
        edges=[FlowEdge(source=s, target=t, label=label) for s, t, label in edges],
    )


def _node(definition: dict[str, Any], node_id: str) -> dict[str, Any]:
    """定義から箱を取り出す。"""
    return next(node for node in definition["nodes"] if node["id"] == node_id)


def test_layout_flow() -> None:
    """上から下の 2 段（正常系）。"""
    # 準備
    graph = _graph("TD", [("a", "b", "x")])
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    assert (result["title"], result["scope"], result["updated"]) == ("図", "文書", "2026-11-03")
    assert (_node(result, "a")["x"], _node(result, "a")["y"]) == (20, 20)
    assert (_node(result, "b")["x"], _node(result, "b")["y"]) == (20, 140)
    wire = result["wires"][0]
    assert wire["id"] == "e1"
    assert wire["points"] == [[100, 76], [100, 140]]
    assert wire["line"] == "flow"
    assert wire["label"] == "x"


def test_layout_flow_when_left_to_right() -> None:
    """左から右（正常系）。"""
    # 準備
    graph = _graph("LR", [("a", "b", None)])
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    assert (_node(result, "b")["x"], _node(result, "b")["y"]) == (244, 20)
    assert result["wires"][0]["points"] == [[180, 48], [244, 48]]


def test_layout_flow_when_branch() -> None:
    """分岐した先を同じ段に並べる（正常系）。"""
    # 準備
    graph = _graph("TD", [("a", "b", None), ("a", "c", None)])
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    b, c = _node(result, "b"), _node(result, "c")
    assert b["y"] == c["y"]
    assert c["x"] == b["x"] + 200
    assert len(result["wires"][1]["points"]) == 4


def test_layout_flow_when_loop() -> None:
    """戻る線（正常系）。"""
    # 準備
    graph = _graph("TD", [("a", "b", None), ("b", "a", None)])
    without_loop = layout_flow(_graph("TD", [("a", "b", None)]), HEAD)
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    wire = result["wires"][1]
    assert wire["line"] == "loop"
    right = max(node["x"] + node["w"] for node in result["nodes"])
    assert any(point[0] > right for point in wire["points"])
    assert result["width"] > without_loop["width"]


def test_layout_flow_when_same_input() -> None:
    """同じ入力に同じ定義（正常系）。"""
    # 準備
    graph = _graph("TD", [("a", "b", "x"), ("b", "c", None), ("c", "a", None)])
    # 実行
    first = layout_flow(graph, HEAD)
    second = layout_flow(graph, HEAD)
    # 検証
    assert first == second


def test_layout_flow_when_self_loop() -> None:
    """元と先が同じ線（正常系）。"""
    # 準備
    graph = _graph("TD", [("a", "b", None), ("b", "b", None)])
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    wire = result["wires"][1]
    b = _node(result, "b")
    center = b["y"] + b["h"] // 2
    assert wire["line"] == "loop"
    assert (wire["points"][0][1], wire["points"][-1][1]) == (center - 14, center + 14)
    assert wire["points"][1][0] > b["x"] + b["w"]
