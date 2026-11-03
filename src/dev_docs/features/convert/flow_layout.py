"""フロー図の中間データの、mdmark のフロー図の部品の定義への配置。"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from dev_docs.features.convert.types import DiagramHead, FlowEdge, FlowGraph

NODE_WIDTH = 160
NODE_HEIGHT = 56
RANK_GAP = 64
ROW_GAP = 40
MARGIN = 20
LOOP_BAND = 40

type Point = tuple[int, int]


def _back_edges(graph: FlowGraph) -> set[int]:
    """箱の出た順の深さ優先でたどり、たどっている途中の箱へ戻る線の番号を返す。"""
    outgoing: dict[str, list[int]] = {node.id: [] for node in graph.nodes}
    for index, edge in enumerate(graph.edges):
        outgoing[edge.source].append(index)
    back: set[int] = set()
    done: set[str] = set()
    for root in outgoing:
        if root in done:
            continue
        # たどっている途中の箱と、その箱から次にたどる線の位置
        stack: list[tuple[str, int]] = [(root, 0)]
        path = {root}
        while stack:
            node, position = stack[-1]
            # 箱から出る線をたどり終えた: 途中の箱から外す
            if position >= len(outgoing[node]):
                stack.pop()
                path.discard(node)
                done.add(node)
                continue
            stack[-1] = (node, position + 1)
            index = outgoing[node][position]
            target = graph.edges[index].target
            # 途中の箱（元と先が同じ線を含む）へ戻る: 戻る線
            if target in path:
                back.add(index)
            # まだたどっていない箱: その箱へ進む
            elif target not in done:
                stack.append((target, 0))
                path.add(target)
    return back


def _ranks(graph: FlowGraph, back: set[int]) -> dict[str, int]:
    """進む線だけで、各箱の段（元の箱からの最長の段数）を決める。"""
    ranks = {node.id: 0 for node in graph.nodes}
    forward = [edge for index, edge in enumerate(graph.edges) if index not in back]
    # 進む線は閉路を持たないため、箱の数だけ繰り返せば最長の段数に定まる
    for _ in graph.nodes:
        changed = False
        for edge in forward:
            if ranks[edge.target] < ranks[edge.source] + 1:
                ranks[edge.target] = ranks[edge.source] + 1
                changed = True
        if not changed:
            break
    return ranks


def _positions(graph: FlowGraph, ranks: dict[str, int]) -> dict[str, Point]:
    """段ごとに箱を出た順に並べ、左上の位置を返す。"""
    top_down = graph.direction == "TD"
    rank_step = (NODE_HEIGHT if top_down else NODE_WIDTH) + RANK_GAP
    row_step = (NODE_WIDTH if top_down else NODE_HEIGHT) + ROW_GAP
    counts: dict[int, int] = {}
    positions: dict[str, Point] = {}
    for node in graph.nodes:
        rank = ranks[node.id]
        order = counts.get(rank, 0)
        counts[rank] = order + 1
        along = MARGIN + rank * rank_step
        across = MARGIN + order * row_step
        positions[node.id] = (across, along) if top_down else (along, across)
    return positions


def _forward_points(top_down: bool, source: Point, target: Point) -> list[Point]:
    """進む線の、先の段の手前 `RANK_GAP / 2` で折れる縦と横の折れ線の点を返す。"""
    if top_down:
        start = (source[0] + NODE_WIDTH // 2, source[1] + NODE_HEIGHT)
        end = (target[0] + NODE_WIDTH // 2, target[1])
        # 同じ列: まっすぐ下ろす
        if start[0] == end[0]:
            return [start, end]
        bend = end[1] - RANK_GAP // 2
        return [start, (start[0], bend), (end[0], bend), end]
    start = (source[0] + NODE_WIDTH, source[1] + NODE_HEIGHT // 2)
    end = (target[0], target[1] + NODE_HEIGHT // 2)
    # 同じ行: まっすぐ右へ引く
    if start[1] == end[1]:
        return [start, end]
    bend = end[0] - RANK_GAP // 2
    return [start, (bend, start[1]), (bend, end[1]), end]


def _loop_points(top_down: bool, source: Point, target: Point, band: int) -> list[Point]:
    """戻る線の、戻りの帯の中央を通る折れ線の点を返す。"""
    # 元と先が同じ線: 出る点と入る点を縁の中央から前後にずらし、幅のある輪にする
    shift = 0
    if source == target:
        shift = NODE_HEIGHT // 4 if top_down else NODE_WIDTH // 4
    if top_down:
        # 上から下: 箱の右の縁から右の帯を通る
        start = (source[0] + NODE_WIDTH, source[1] + NODE_HEIGHT // 2 - shift)
        end = (target[0] + NODE_WIDTH, target[1] + NODE_HEIGHT // 2 + shift)
        return [start, (band, start[1]), (band, end[1]), end]
    # 左から右: 箱の下の縁から下の帯を通る
    start = (source[0] + NODE_WIDTH // 2 - shift, source[1] + NODE_HEIGHT)
    end = (target[0] + NODE_WIDTH // 2 + shift, target[1] + NODE_HEIGHT)
    return [start, (start[0], band), (end[0], band), end]


def _label_at(points: list[Point]) -> list[int]:
    """線の最も長い区間の中央を返す。"""
    segments = list(pairwise(points))
    (x1, y1), (x2, y2) = max(
        segments,
        key=lambda segment: abs(segment[1][0] - segment[0][0]) + abs(segment[1][1] - segment[0][1]),
    )
    return [(x1 + x2) // 2, (y1 + y2) // 2]


def _wire(index: int, edge: FlowEdge, points: list[Point], line: str) -> dict[str, Any]:
    """線の定義を作る（`id` は出た順の `e{n}`）。"""
    wire: dict[str, Any] = {
        "id": f"e{index + 1}",
        "from": edge.source,
        "to": edge.target,
        "line": line,
        "points": [list(point) for point in points],
    }
    if edge.label:
        wire["label"] = edge.label
        wire["labelAt"] = _label_at(points)
    return wire


def layout_flow(graph: FlowGraph, head: DiagramHead) -> dict[str, Any]:
    """フロー図の中間データの箱と線に座標を付け、mdmark のフロー図の部品の定義にする。"""
    top_down = graph.direction == "TD"
    back = _back_edges(graph)
    positions = _positions(graph, _ranks(graph, back))
    right = max((x + NODE_WIDTH for x, _ in positions.values()), default=MARGIN)
    bottom = max((y + NODE_HEIGHT for _, y in positions.values()), default=MARGIN)
    band = (right if top_down else bottom) + LOOP_BAND // 2
    # 線: 戻る線は帯を通し、それ以外は先の段の手前で折る
    wires = [
        _wire(
            index,
            edge,
            _loop_points(top_down, positions[edge.source], positions[edge.target], band)
            if index in back
            else _forward_points(top_down, positions[edge.source], positions[edge.target]),
            "loop" if index in back else "flow",
        )
        for index, edge in enumerate(graph.edges)
    ]
    # 図の大きさ: 戻る線があれば帯の側に帯の幅を足す
    width = right + MARGIN + (LOOP_BAND if back and top_down else 0)
    height = bottom + MARGIN + (LOOP_BAND if back and not top_down else 0)
    nodes: list[dict[str, Any]] = []
    for node in graph.nodes:
        x, y = positions[node.id]
        item: dict[str, Any] = {
            "id": node.id,
            "kind": node.kind,
            "x": x,
            "y": y,
            "w": NODE_WIDTH,
            "h": NODE_HEIGHT,
            "name": node.name,
        }
        if node.sub:
            item["sub"] = node.sub
        nodes.append(item)
    return {
        "title": head.title,
        "scope": head.scope,
        "updated": head.updated,
        "width": width,
        "height": height,
        "nodes": nodes,
        "wires": wires,
    }
