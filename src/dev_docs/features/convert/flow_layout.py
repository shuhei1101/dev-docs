"""フロー図の中間データの、mdmark のフロー図の部品の定義への配置。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from dev_docs.features.convert.types import DiagramHead, FlowEdge, FlowGraph

NODE_WIDTH = 160
NODE_HEIGHT = 56
RANK_GAP = 64
ROW_GAP = 40
MARGIN = 20
FRAME_PADDING = 20
# ノードの文字の大きさ・行の高さの倍率・余白（px）と半角の幅の割合。mdmark の文字の収まりの判定と同じ値
LABEL_METRICS = {
    "kind_size": 11,
    "name_size": 14,
    "line_height": 1.4,
    "pad_x": 10,
    "pad_y": 6,
    "half_width": 0.6,
}
# 半角とみなす文字の範囲（U+007E 以下と半角カナ）。mdmark の文字の収まりの判定と同じ範囲
_HALF_WIDTH_LAST = 0x7E
_HALF_KANA = (0xFF61, 0xFF9F)

type Point = tuple[int, int]
# ノードの左上と大きさ（x, y, w, h）
type Box = tuple[int, int, int, int]
# 通り道の鍵（線の番号, レイヤー）
type LaneKey = tuple[int, int]


def _back_edges(graph: FlowGraph) -> set[int]:
    """ノードの出た順の深さ優先でたどり、たどっている途中のノードへ戻る線の番号を返却する。"""
    outgoing: dict[str, list[int]] = {node.id: [] for node in graph.nodes}
    for index, edge in enumerate(graph.edges):
        outgoing[edge.source].append(index)
    back: set[int] = set()
    done: set[str] = set()
    for root in outgoing:
        if root in done:
            continue
        # たどっている途中のノードと、そのノードから次にたどる線の位置
        stack: list[tuple[str, int]] = [(root, 0)]
        path = {root}
        while stack:
            node, position = stack[-1]
            # ノードから出る線をたどり終えた: 途中のノードから除外する
            if position >= len(outgoing[node]):
                stack.pop()
                path.discard(node)
                done.add(node)
                continue
            stack[-1] = (node, position + 1)
            index = outgoing[node][position]
            target = graph.edges[index].target
            # 途中のノード（元と先が同じ線を含む）へ戻る: 戻る線
            if target in path:
                back.add(index)
            # まだたどっていないノード: そのノードへ進む
            elif target not in done:
                stack.append((target, 0))
                path.add(target)
    return back


def _ranks(graph: FlowGraph, back: set[int]) -> dict[str, int]:
    """進む線だけで、各ノードのレイヤー（元のノードからの最長のレイヤー数）を決める。"""
    ranks = {node.id: 0 for node in graph.nodes}
    forward = [edge for index, edge in enumerate(graph.edges) if index not in back]
    # 進む線は閉路を持たないため、ノードの数だけ繰り返せば最長のレイヤー数に定まる
    for _ in graph.nodes:
        changed = False
        for edge in forward:
            if ranks[edge.target] < ranks[edge.source] + 1:
                ranks[edge.target] = ranks[edge.source] + 1
                changed = True
        if not changed:
            break
    return ranks


def _is_wide(char: str) -> bool:
    """文字を全角とみなすか（mdmark の判定と同じく、U+007E 以下と半角カナだけを半角とみなす）。"""
    code = ord(char)
    return not (code <= _HALF_WIDTH_LAST or _HALF_KANA[0] <= code <= _HALF_KANA[1])


def _label_lines(text: str, width: float) -> int:
    """全角を文字の大きさ、半角をその `half_width` 倍の幅とみなし、幅で改行した行の数を返却する。"""
    if not text:
        return 0
    size = LABEL_METRICS["name_size"]
    lines, used = 1, 0.0
    for char in text:
        advance = size if _is_wide(char) else size * LABEL_METRICS["half_width"]
        # 行に 1 文字も無いときは、幅を超えても同じ行に配置する
        if used > 0 and used + advance > width:
            lines += 1
            used = 0.0
        used += advance
    return lines


def _node_height(name: str) -> int:
    """名前が改行して収まるノードの高さを返却する（`NODE_HEIGHT` より低くはしない）。"""
    width = NODE_WIDTH - LABEL_METRICS["pad_x"] * 2
    lines = _label_lines(name, width)
    text = (LABEL_METRICS["kind_size"] + lines * LABEL_METRICS["name_size"]) * LABEL_METRICS[
        "line_height"
    ]
    return max(NODE_HEIGHT, math.ceil(text + LABEL_METRICS["pad_y"] * 2))


@dataclass(frozen=True)
class _Placement:
    """ノードと通り道の位置（`across` は同じレイヤーの並びの向き、`along` はレイヤーの向きの座標）。"""

    across: dict[str, int]
    rank_start: dict[int, int]
    rank_size: dict[int, int]
    lanes: dict[LaneKey, int]
    # 全てのレイヤーの、フレームの中のノードと通り道の最も遠い端（フレームの中のノードが無ければ `None`）
    frame_end: int | None


def _members(graph: FlowGraph) -> frozenset[str]:
    """フレームの中のノードのうち、配置されているノードの ID を返却する。"""
    if graph.frame is None:
        return frozenset()
    known = {node.id for node in graph.nodes}
    return graph.frame.nodes & known


def _lanes(graph: FlowGraph, ranks: dict[str, int]) -> list[tuple[int, int, bool]]:
    """レイヤーを 2 つ以上飛ばす線の、間のレイヤーごとの通り道（線の番号・レイヤー・フレームの中か）を出た順に返却する。"""
    members = _members(graph)
    lanes: list[tuple[int, int, bool]] = []
    for index, edge in enumerate(graph.edges):
        low, high = sorted((ranks[edge.source], ranks[edge.target]))
        inner = edge.source in members and edge.target in members
        lanes += [(index, rank, inner) for rank in range(low + 1, high)]
    return lanes


def _place(graph: FlowGraph, ranks: dict[str, int], heights: dict[str, int]) -> _Placement:
    """レイヤーごとに、フレームの中のノード・フレームの中の通り道・フレームの外のノード・フレームの外の通り道の順に並べる。"""
    top_down = graph.direction == "TD"
    members = _members(graph)
    has_frame = bool(members)
    origin = MARGIN + (FRAME_PADDING if has_frame else 0)
    lanes = _lanes(graph, ranks)
    # 並べる要素: (レイヤー, ノードの ID か通り道の鍵, 並びの向きの大きさ)
    inside: list[tuple[int, str | LaneKey, int]] = []
    outside: list[tuple[int, str | LaneKey, int]] = []
    for node in graph.nodes:
        item = (ranks[node.id], node.id, NODE_WIDTH if top_down else heights[node.id])
        (inside if node.id in members else outside).append(item)
    inner_lanes: list[tuple[int, str | LaneKey, int]] = [
        (rank, (index, rank), 0) for index, rank, inner in lanes if inner
    ]
    outer_lanes: list[tuple[int, str | LaneKey, int]] = [
        (rank, (index, rank), 0) for index, rank, inner in lanes if not inner
    ]

    across: dict[str, int] = {}
    lane_across: dict[LaneKey, int] = {}
    # レイヤーごとの、並べ終えた最後の要素の端
    cursor: dict[int, int] = {}

    def lay(items: list[tuple[int, str | LaneKey, int]], start: int) -> None:
        """要素をレイヤーごとに `ROW_GAP` を空けて並べる（レイヤーの最初の要素は `start` に配置する）。"""
        for rank, key, size in items:
            position = cursor[rank] + ROW_GAP if rank in cursor else start
            # 通り道: 鍵は（線の番号, レイヤー）のタプル
            if isinstance(key, tuple):
                lane_across[key] = position
            # ノード: 鍵はノードの ID
            else:
                across[key] = position
            cursor[rank] = position + size

    lay(inside + inner_lanes, origin)
    frame_end = max(cursor.values()) if has_frame and cursor else None
    # フレームの外は、全てのレイヤーの、フレームの中の最も遠い端から余白の 2 倍を空けた位置より先に並べる
    outside_start = frame_end + FRAME_PADDING * 2 if frame_end is not None else origin
    cursor = {rank: max(end, outside_start - ROW_GAP) for rank, end in cursor.items()}
    lay(outside + outer_lanes, outside_start)

    # レイヤーの厚みは、そのレイヤーで最も大きいノードに合わせる
    rank_size: dict[int, int] = {}
    for node in graph.nodes:
        rank = ranks[node.id]
        depth = heights[node.id] if top_down else NODE_WIDTH
        rank_size[rank] = max(rank_size.get(rank, 0), depth)
    rank_start: dict[int, int] = {}
    along = origin
    for rank in sorted(rank_size):
        rank_start[rank] = along
        along += rank_size[rank] + RANK_GAP
    return _Placement(
        across=across,
        rank_start=rank_start,
        rank_size=rank_size,
        lanes=lane_across,
        frame_end=frame_end,
    )


def _simplify(points: list[Point]) -> list[Point]:
    """続けて同じ点と、一直線に並ぶ途中の点を除く。"""
    unique: list[Point] = []
    for point in points:
        if not unique or unique[-1] != point:
            unique.append(point)
    result: list[Point] = []
    for point in unique:
        # 直前の 2 点と縦か横に一直線に並ぶ: 途中の点を今の点に置き換える
        if len(result) > 1:
            (x1, y1), (x2, y2) = result[-2], result[-1]
            if (x1 == x2 == point[0]) or (y1 == y2 == point[1]):
                result[-1] = point
                continue
        result.append(point)
    return result


def _route(top_down: bool, path: list[Point]) -> list[Point]:
    """（並びの向き・レイヤーの向き）の点の並びを、図の座標の折れ線にする。"""
    points = [(across, along) if top_down else (along, across) for across, along in path]
    return _simplify(points)


def _gap_start(placement: _Placement, rank: int) -> int:
    """レイヤーとその次のレイヤーの間の隙間の、レイヤーの側の端。"""
    return placement.rank_start[rank] + placement.rank_size[rank]


def _forward_path(
    placement: _Placement, index: int, source: Box, target: Box, ranks: tuple[int, int]
) -> list[Point]:
    """進む線: 元の出口の辺の中央から、隙間の中央で折れ、通り道を順に通り、先の入口の辺の中央へ。"""
    s_across, s_along, s_size, s_depth = source
    t_across, t_along, t_size, _ = target
    low, high = ranks
    current = s_across + s_size // 2
    path = [(current, s_along + s_depth)]
    for rank in range(low, high):
        bend = _gap_start(placement, rank) + RANK_GAP // 2
        path.append((current, bend))
        # 次のレイヤーが先のノードのレイヤーでなければ、そのレイヤーの通り道へ合わせる
        current = placement.lanes[(index, rank + 1)] if rank + 1 < high else t_across + t_size // 2
        path.append((current, bend))
    path.append((current, t_along))
    return path


def _back_path(
    placement: _Placement, index: int, source: Box, target: Box, ranks: tuple[int, int]
) -> list[Point]:
    """戻る線: 元の入口の辺のずらした点から、隙間の 1/4 で折れ、通り道を逆に通り、先の出口の辺へ。"""
    s_across, s_along, s_size, _ = source
    t_across, t_along, t_size, t_depth = target
    high, low = ranks
    current = s_across + s_size // 2 + s_size // 4
    path = [(current, s_along)]
    for rank in range(high - 1, low - 1, -1):
        bend = _gap_start(placement, rank) + RANK_GAP // 4
        path.append((current, bend))
        # 次のレイヤーが先のノードのレイヤーでなければ、そのレイヤーの通り道へ合わせる
        current = (
            placement.lanes[(index, rank)] if rank > low else t_across + t_size // 2 + t_size // 4
        )
        path.append((current, bend))
    path.append((current, t_along + t_depth))
    return path


def _self_loop(top_down: bool, box: Box) -> list[Point]:
    """元と先が同じ線: ノードの横の辺から `ROW_GAP` の半分だけ張り出す輪。"""
    x, y, width, height = box
    reach = ROW_GAP // 2
    # 上から下: 右の辺から右へ張り出す
    if top_down:
        right = x + width
        upper, lower = y + height // 2 - height // 4, y + height // 2 + height // 4
        return [(right, upper), (right + reach, upper), (right + reach, lower), (right, lower)]
    # 左から右: 下の辺から下へ張り出す
    bottom = y + height
    left, right = x + width // 2 - width // 4, x + width // 2 + width // 4
    return [(left, bottom), (left, bottom + reach), (right, bottom + reach), (right, bottom)]


def _label_at(points: list[Point]) -> list[int]:
    """線の最も長い区間の中央を返却する。"""
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
    if edge.tip:
        wire["tip"] = edge.tip
    return wire


def _frame(title: str, boxes: list[Box], lanes: list[Point]) -> dict[str, Any]:
    """フレームの中のノードと通り道を余白つきで囲むフレームの定義を作る。"""
    xs = [x for x, _, _, _ in boxes] + [x for x, _ in lanes]
    ys = [y for _, y, _, _ in boxes] + [y for _, y in lanes]
    rights = [x + w for x, _, w, _ in boxes] + [x for x, _ in lanes]
    bottoms = [y + h for _, y, _, h in boxes] + [y for _, y in lanes]
    left, top = min(xs) - FRAME_PADDING, min(ys) - FRAME_PADDING
    right, bottom = max(rights) + FRAME_PADDING, max(bottoms) + FRAME_PADDING
    return {"title": title, "x": left, "y": top, "w": right - left, "h": bottom - top}


def layout_flow(graph: FlowGraph, head: DiagramHead) -> dict[str, Any]:
    """フロー図の中間データのノードと線に座標を付け、mdmark のフロー図の部品の定義にする。"""
    top_down = graph.direction == "TD"
    back = _back_edges(graph)
    ranks = _ranks(graph, back)
    heights = {node.id: _node_height(node.name) for node in graph.nodes}
    placement = _place(graph, ranks, heights)
    # ノードの左上と大きさ
    boxes: dict[str, Box] = {}
    for node in graph.nodes:
        across, along = placement.across[node.id], placement.rank_start[ranks[node.id]]
        x, y = (across, along) if top_down else (along, across)
        boxes[node.id] = (x, y, NODE_WIDTH, heights[node.id])

    def oriented(node_id: str) -> Box:
        """ノードの（並びの向きの位置・レイヤーの向きの位置・並びの向きの大きさ・レイヤーの向きの大きさ）。"""
        x, y, width, height = boxes[node_id]
        return (x, y, width, height) if top_down else (y, x, height, width)

    # 線: 元と先が同じ線は輪、戻る線は通り道を逆に、進む線は通り道を順にたどる
    wires: list[dict[str, Any]] = []
    for index, edge in enumerate(graph.edges):
        rank_pair = (ranks[edge.source], ranks[edge.target])
        # 元と先が同じ線: ノードの横の辺から張り出す輪
        if edge.source == edge.target:
            points = _self_loop(top_down, boxes[edge.source])
        # 戻る線: 元の入口の辺から先の出口の辺へ
        elif index in back:
            path = _back_path(
                placement, index, oriented(edge.source), oriented(edge.target), rank_pair
            )
            points = _route(top_down, path)
        # 進む線: 元の出口の辺から先の入口の辺へ
        else:
            path = _forward_path(
                placement, index, oriented(edge.source), oriented(edge.target), rank_pair
            )
            points = _route(top_down, path)
        wires.append(_wire(index, edge, points, "loop" if index in back else edge.line))

    # フレーム: 中のノードが 1 つ以上配置されていれば、中のノードとフレームの中の通り道を囲む
    frame = None
    members = _members(graph)
    if graph.frame is not None and members:
        lane_points: list[Point] = []
        for index, rank in placement.lanes:
            edge = graph.edges[index]
            # 元と先がどちらもフレームの中のノードである線の通り道だけを囲む
            if edge.source not in members or edge.target not in members:
                continue
            across = placement.lanes[(index, rank)]
            for along in (
                _gap_start(placement, rank) - placement.rank_size[rank],
                _gap_start(placement, rank),
            ):
                lane_points.append((across, along) if top_down else (along, across))
        frame = _frame(
            graph.frame.label,
            [boxes[node_id] for node_id in boxes if node_id in members],
            lane_points,
        )

    # 図の大きさ: 全てのノード・線の点・フレームが余白つきで収まる
    rights = [x + w for x, _, w, _ in boxes.values()]
    bottoms = [y + h for _, y, _, h in boxes.values()]
    for wire in wires:
        rights += [x for x, _ in wire["points"]]
        bottoms += [y for _, y in wire["points"]]
    if frame is not None:
        rights.append(frame["x"] + frame["w"])
        bottoms.append(frame["y"] + frame["h"])
    width = max(rights, default=0) + MARGIN
    height = max(bottoms, default=0) + MARGIN

    nodes: list[dict[str, Any]] = []
    for node in graph.nodes:
        x, y, node_width, node_height = boxes[node.id]
        item: dict[str, Any] = {
            "id": node.id,
            "kind": node.kind,
            "x": x,
            "y": y,
            "w": node_width,
            "h": node_height,
            "name": node.name,
        }
        if node.hint:
            item["hint"] = node.hint
        nodes.append(item)
    definition: dict[str, Any] = {
        "title": head.title,
        "scope": head.scope,
        "updated": head.updated,
        "width": width,
        "height": height,
    }
    if frame is not None:
        definition["frame"] = frame
    definition["nodes"] = nodes
    definition["wires"] = wires
    return definition
