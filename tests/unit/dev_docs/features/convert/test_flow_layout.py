from __future__ import annotations

from itertools import pairwise
from typing import Any

from dev_docs.features.convert.flow_layout import layout_flow
from dev_docs.features.convert.types import DiagramHead, FlowEdge, FlowFrame, FlowGraph, FlowNode

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


def _with_frame(graph: FlowGraph, members: set[str]) -> FlowGraph:
    """中間データに、表示 `枠` で `members` を中の箱にした枠を付ける。"""
    return FlowGraph(
        direction=graph.direction,
        nodes=graph.nodes,
        edges=graph.edges,
        frame=FlowFrame(label="枠", nodes=frozenset(members)),
    )


def _crosses(points: list[list[int]], box: dict[str, Any]) -> bool:
    """縦と横の折れ線のどれかの区間が、矩形の内側を通るか（辺をなぞる・角に触れるだけは通らない）。"""
    left, top = box["x"], box["y"]
    right, bottom = left + box["w"], top + box["h"]
    for (x1, y1), (x2, y2) in pairwise(points):
        low_x, high_x = sorted((x1, x2))
        low_y, high_y = sorted((y1, y2))
        # 縦の区間: x が矩形の内側にあり、y の範囲が矩形と重なるか
        if x1 == x2 and left < x1 < right and low_y < bottom and top < high_y:
            return True
        # 横の区間: y が矩形の内側にあり、x の範囲が矩形と重なるか
        if y1 == y2 and top < y1 < bottom and low_x < right and left < high_x:
            return True
    return False


def _overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """2 つの矩形の内側が重なるか。"""
    return (
        a["x"] < b["x"] + b["w"]
        and b["x"] < a["x"] + a["w"]
        and a["y"] < b["y"] + b["h"]
        and b["y"] < a["y"] + a["h"]
    )


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
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    wire = result["wires"][1]
    assert wire["line"] == "loop"
    # b の上の辺から a の下の辺へ
    assert wire["points"] == [[140, 140], [140, 76]]
    assert result["width"] == 200


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
    assert wire["line"] == "loop"
    # b の右の辺から ROW_GAP / 2 張り出す輪
    assert wire["points"] == [[180, 154], [200, 154], [200, 182], [180, 182]]
    assert result["width"] == 220


def test_layout_flow_when_line_and_tips() -> None:
    """線の種類・詳細と箱の説明（正常系）。"""
    # 準備
    graph = FlowGraph(
        direction="TD",
        nodes=[
            FlowNode(id="a", name="A", kind="script", hint="説明"),
            FlowNode(id="b", name="B", kind="script"),
        ],
        edges=[FlowEdge(source="a", target="b", label="x", line="read", tip="y")],
    )
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    wire = result["wires"][0]
    assert (wire["line"], wire["tip"]) == ("read", "y")
    assert _node(result, "a")["hint"] == "説明"
    assert "hint" not in _node(result, "b")


def test_layout_flow_when_frame() -> None:
    """枠（正常系）。"""
    # 準備
    base = _graph("TD", [("a", "b", None), ("b", "c", None)])
    graph = FlowGraph(
        direction=base.direction,
        nodes=base.nodes,
        edges=base.edges,
        frame=FlowFrame(label="判定", nodes=frozenset({"a", "b"})),
    )
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    assert (_node(result, "a")["x"], _node(result, "a")["y"]) == (40, 40)
    assert (_node(result, "c")["x"], _node(result, "c")["y"]) == (240, 280)
    assert result["frame"] == {"title": "判定", "x": 20, "y": 20, "w": 200, "h": 216}
    assert not _overlaps(_node(result, "c"), result["frame"])
    assert (result["width"], result["height"]) == (420, 356)


def test_layout_flow_when_frame_without_nodes() -> None:
    """中の箱が置かれていない枠（正常系）。"""
    # 準備
    graph = FlowGraph(
        direction="TD",
        nodes=[FlowNode(id="a", name="A", kind="script")],
        edges=[],
        frame=FlowFrame(label="枠", nodes=frozenset({"z"})),
    )
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    assert "frame" not in result
    assert (_node(result, "a")["x"], _node(result, "a")["y"]) == (20, 20)


def test_layout_flow_when_skip_rank() -> None:
    """段を飛ばす線（正常系）。"""
    # 準備
    graph = _graph("TD", [("a", "b", None), ("b", "c", None), ("a", "c", None)])
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    assert _node(result, "c")["y"] == 260
    points = result["wires"][2]["points"]
    assert points == [[100, 76], [100, 108], [220, 108], [220, 228], [100, 228], [100, 260]]
    assert not _crosses(points, _node(result, "b"))


def test_layout_flow_when_skip_rank_left_to_right() -> None:
    """左から右の段を飛ばす線（正常系）。"""
    # 準備
    graph = _graph("LR", [("a", "b", None), ("b", "c", None), ("a", "c", None)])
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    a, b, c = _node(result, "a"), _node(result, "b"), _node(result, "c")
    assert a["x"] < b["x"] < c["x"]
    assert c["x"] == max(node["x"] for node in result["nodes"])
    assert not _crosses(result["wires"][2]["points"], b)


def test_layout_flow_when_back_edge_skip_rank() -> None:
    """段を飛ばして戻る線（正常系）。"""
    # 準備
    graph = _graph("TD", [("a", "b", None), ("b", "c", None), ("c", "a", None)])
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    a, b, c = _node(result, "a"), _node(result, "b"), _node(result, "c")
    wire = result["wires"][2]
    assert wire["line"] == "loop"
    # c の上の辺から出て a の下の辺へ入る
    assert wire["points"][0][1] == c["y"]
    assert wire["points"][-1][1] == a["y"] + a["h"]
    assert not _crosses(wire["points"], b)
    # 戻る線で段は増えない
    assert c["y"] == 260


def test_layout_flow_when_self_loop_beside_node() -> None:
    """同じ段に箱が並ぶ元と先が同じ線（正常系）。"""
    # 準備
    graph = FlowGraph(
        direction="TD",
        nodes=[
            FlowNode(id="a", name="A", kind="script"),
            FlowNode(id="b", name="B", kind="script"),
        ],
        edges=[FlowEdge(source="a", target="a")],
    )
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    a, b = _node(result, "a"), _node(result, "b")
    points = result["wires"][0]["points"]
    right = a["x"] + a["w"]
    assert all(right <= x <= right + 20 for x, _ in points)
    assert not _crosses(points, b)


def test_layout_flow_when_long_name() -> None:
    """折り返す名前（正常系）。"""
    # 準備
    graph = FlowGraph(
        direction="TD",
        nodes=[
            FlowNode(id="a", name="あ" * 30, kind="script"),
            FlowNode(id="b", name="B", kind="script"),
        ],
        edges=[FlowEdge(source="a", target="b")],
    )
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    a, b = _node(result, "a"), _node(result, "b")
    assert (a["h"], b["h"]) == (87, 56)
    assert b["y"] == 171
    assert not _overlaps(a, b)


def test_layout_flow_when_half_width_name() -> None:
    """半角を含む名前（正常系）。"""
    # 準備
    graph = FlowGraph(
        direction="TD", nodes=[FlowNode(id="a", name="x" * 30, kind="script")], edges=[]
    )
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    assert _node(result, "a")["h"] == 67


def test_layout_flow_when_frame_outside_rank() -> None:
    """枠の中の箱が無い段の枠の外の箱（正常系）。"""
    # 準備
    graph = _with_frame(_graph("TD", [("a", "b", None), ("b", "c", None)]), {"a", "c"})
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    assert not _overlaps(_node(result, "b"), result["frame"])


def test_layout_flow_when_frame_skip_rank() -> None:
    """枠の中の箱どうしの段を飛ばす線（正常系）。"""
    # 準備
    graph = _with_frame(
        _graph("LR", [("a", "b", None), ("b", "c", None), ("a", "c", None)]), {"a", "b", "c"}
    )
    # 実行
    result = layout_flow(graph, HEAD)
    # 検証
    frame = result["frame"]
    points = result["wires"][2]["points"]
    assert all(
        frame["x"] <= x <= frame["x"] + frame["w"] and frame["y"] <= y <= frame["y"] + frame["h"]
        for x, y in points
    )
    assert not _crosses(points, _node(result, "b"))
