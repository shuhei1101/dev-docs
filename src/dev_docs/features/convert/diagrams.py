"""`x-diagram` の値と手で記載する Mermaid の、mdmark の図の部品か Mermaid のコードブロックへの描画。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal, cast

from dev_docs.features.convert.flow_layout import layout_flow
from dev_docs.features.convert.mermaid import parse_mermaid
from dev_docs.features.convert.types import (
    DiagramHead,
    DiagramKind,
    FlowEdge,
    FlowFrame,
    FlowGraph,
    FlowNode,
    LineKind,
    NodeKind,
)

FLOW_KINDS = ("flowchart", "dataflow", "architecture", "state")
LEFT_TO_RIGHT_KINDS = ("dataflow", "architecture")
# `x-diagram` のノードの `kind` から mdmark のノードの種類
NODE_KINDS: dict[str, NodeKind] = {
    "actor": "external",
    "external": "external",
    "process": "script",
    "system": "script",
    "store": "data",
    "start": "start",
    "question": "question",
    "action": "action",
    "result": "result",
}
# `kind` が無いノードと、`NODE_KINDS` に無い `kind` のノードの種類（スキーマの既定）
DEFAULT_NODE_KIND = "process"
# 辺の `line` に記載できる線の種類
LINE_KINDS: tuple[LineKind, ...] = ("flow", "read", "write", "reply", "loop")
# `line` が無い辺と、`LINE_KINDS` に無い `line` の辺の種類
DEFAULT_LINE: LineKind = "flow"
# 状態遷移の図の始点・終点のノードの ID と名前
STATE_START = ("start", "開始")
STATE_END = ("end", "終了")
# 遷移の `from` のこの値は、`representative` の状態から線を描く
ALL_STATES = "全状態"
# 遷移の `to` のこの値は、`representative` の状態へ線を描く
PREVIOUS_STATE = "元の状態"
# 関連の両端に記載できる多重度（mdmark の ER 図の部品の多重度と同じ値）
ER_CARDINALITIES = ("1", "0..1", "1..n", "0..n")
# 実体の列の `key` から、mdmark の ER 図の部品の列のマーカー
ER_COLUMN_KEYS = {"PK": "pk", "FK": "fk"}
# ER 図のテーブルを格子に配置する寸法（px）。`head`・`row`・`frame` は mdmark の ER 図の寸法と同じ値
ER_LAYOUT = {
    "per_row": 3,
    "width": 240,
    "gap_x": 96,
    "gap_y": 48,
    "margin": 24,
    "head": 44,
    "row": 26,
    "frame": 4,
}


def _items(value: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """値の配列のうち、辞書の要素だけを取り出す。"""
    items = value.get(key)
    return [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []


def _block(marker: str, definition: Mapping[str, Any]) -> str:
    """mdmark の図の部品の範囲に、定義の JSON のコードブロックを配置する。"""
    code = json.dumps(definition, ensure_ascii=False, indent=2)
    return f"<!-- {marker} -->\n\n```json\n{code}\n```\n\n<!-- /{marker} -->"


def _node_kind(node: Mapping[str, Any]) -> NodeKind:
    """ノードの `kind` から mdmark のノードの種類を決める。"""
    return NODE_KINDS.get(str(node.get("kind", DEFAULT_NODE_KIND)), NODE_KINDS[DEFAULT_NODE_KIND])


def _line(edge: Mapping[str, Any]) -> LineKind:
    """辺の `line` から線の種類を決める。"""
    line = edge.get("line")
    return cast("LineKind", line) if line in LINE_KINDS else DEFAULT_LINE


def _text(value: Any) -> str | None:
    """値があれば文字列にする。"""
    return str(value) if value else None


def _flow_graph(value: Mapping[str, Any], kind: DiagramKind) -> FlowGraph:
    """flow 系の値を中間データにする（`clicks` は描かない）。"""
    # 向き: 指定があればその値、無ければ図の種類の既定
    direction: Literal["TD", "LR"] = (
        cast("Literal['TD', 'LR']", value["direction"])
        if value.get("direction") in ("TD", "LR")
        else "LR"
        if kind in LEFT_TO_RIGHT_KINDS
        else "TD"
    )
    nodes = [
        FlowNode(
            id=str(node["id"]),
            name=str(node.get("label", node["id"])),
            kind=_node_kind(node),
            hint=_text(node.get("hint")),
        )
        for node in _items(value, "nodes")
    ]
    known = {node.id for node in nodes}
    edges: list[FlowEdge] = []
    for edge in _items(value, "edges"):
        source, target = str(edge["from"]), str(edge["to"])
        # 宣言の無い端のノード: 名前を ID にして追加する
        for end in (source, target):
            if end not in known:
                nodes.append(FlowNode(id=end, name=end, kind=NODE_KINDS[DEFAULT_NODE_KIND]))
                known.add(end)
        edges.append(
            FlowEdge(
                source=source,
                target=target,
                label=_text(edge.get("label")),
                line=_line(edge),
                tip=_text(edge.get("tip")),
            )
        )
    frame_value = value.get("frame")
    frame = (
        FlowFrame(
            label=str(frame_value.get("label", "")),
            nodes=frozenset(str(node_id) for node_id in frame_value.get("nodes") or []),
        )
        if isinstance(frame_value, Mapping)
        else None
    )
    return FlowGraph(direction=direction, nodes=nodes, edges=edges, frame=frame)


def _state_ends(transition: Mapping[str, Any]) -> tuple[str, str]:
    """遷移の元と先（`全状態`・`元の状態` は `representative` へ置き換える）。"""
    source = str(transition.get("from", ""))
    target = str(transition.get("to", ""))
    if source == ALL_STATES:
        source = str(transition.get("representative", ""))
    if target == PREVIOUS_STATE:
        target = str(transition.get("representative", ""))
    return source, target


def _state_label(transition: Mapping[str, Any]) -> str | None:
    """遷移のラベル（`{trigger} [{condition}]`。どちらも無ければ `None`）。"""
    parts = [
        str(transition["trigger"]) if transition.get("trigger") else "",
        f"[{transition['condition']}]" if transition.get("condition") else "",
    ]
    return " ".join(part for part in parts if part) or None


def _state_graph(value: Mapping[str, Any]) -> FlowGraph:
    """状態遷移の値を、始点・終点と状態のノード、遷移の線にした中間データにする。"""
    transitions = _items(value, "transitions")
    names: list[str] = [str(item["name"]) for item in _items(value, "states")]
    # 遷移の端に出た `states` に無い状態も追加する
    for transition in transitions:
        for end in _state_ends(transition):
            if end and end not in names:
                names.append(end)
    ids = {name: f"s{index + 1}" for index, name in enumerate(names)}
    nodes = [FlowNode(id=STATE_START[0], name=STATE_START[1], kind="start")]
    nodes += [FlowNode(id=ids[name], name=name, kind="action") for name in names]
    edges: list[FlowEdge] = []
    # 始点から初期状態へ
    initial = value.get("initial")
    if initial is not None and str(initial) in ids:
        edges.append(FlowEdge(source=STATE_START[0], target=ids[str(initial)]))
    for transition in transitions:
        source, target = _state_ends(transition)
        # `representative` が無く端が決まらない遷移: 線を描かない（図の元データの表に残る）
        if source not in ids or target not in ids:
            continue
        edges.append(
            FlowEdge(
                source=ids[source],
                target=ids[target],
                label=_state_label(transition),
                # 元と先が同じ遷移は戻る線
                line="loop" if source == target else DEFAULT_LINE,
            )
        )
    final = value.get("final")
    finals = [str(name) for name in final if str(name) in ids] if isinstance(final, list) else []
    # 終了状態があれば、終点を配置して各終了状態から線を描く
    if finals:
        nodes.append(FlowNode(id=STATE_END[0], name=STATE_END[1], kind="result"))
        edges += [FlowEdge(source=ids[name], target=STATE_END[0]) for name in finals]
    return FlowGraph(direction="TD", nodes=nodes, edges=edges)


def _er_table_columns(table: Mapping[str, Any]) -> list[dict[str, Any]]:
    """ER 図のテンプレートのテーブルの列を、ER 図の部品の列にする。"""
    columns: list[dict[str, Any]] = []
    for column in _items(table, "columns"):
        item: dict[str, Any] = {"name": str(column["name"]), "type": str(column.get("type", ""))}
        if column.get("title"):
            item["desc"] = str(column["title"])
        for key, flag in (("primary_key", "pk"), ("foreign_key", "fk"), ("not_null", "nn")):
            if column.get(key):
                item[flag] = True
        columns.append(item)
    return columns


def _er_entity_columns(entity: Mapping[str, Any]) -> list[dict[str, Any]]:
    """実体の `columns` を、ER 図の部品の列にする。"""
    columns: list[dict[str, Any]] = []
    for column in _items(entity, "columns"):
        item: dict[str, Any] = {"name": str(column["name"]), "type": str(column.get("type", ""))}
        flag = ER_COLUMN_KEYS.get(str(column.get("key")))
        if flag is not None:
            item[flag] = True
        columns.append(item)
    return columns


def er_table_titles(tables: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """同じ文書の `tables[]` から、テーブルの物理名と論理名のどちらからも論理名を検索する表を作る。"""
    titles: dict[str, str] = {}
    for table in tables:
        # 論理名を持たないテーブルは、適用する見出し・実体が無いため入れない
        if table.get("title") is None:
            continue
        for key in ("name", "title"):
            if table.get(key) is not None:
                # 重なるキーは先に出たテーブルを残す
                titles.setdefault(str(table[key]), str(table["title"]))
    return titles


class _ErModel:
    """ER 図の実体ごとのテーブルと列の引き方。"""

    def __init__(self, value: Mapping[str, Any], tables: Sequence[Mapping[str, Any]]) -> None:
        self.by_title = {str(table.get("title")): table for table in tables}
        self.entities = _items(value, "entities")

    def table(self, entity: Mapping[str, Any]) -> Mapping[str, Any] | None:
        """実体の `name` が `title` に該当するテーブルを返却する。"""
        return self.by_title.get(str(entity.get("name")))

    def columns(self, entity: Mapping[str, Any]) -> list[dict[str, Any]]:
        """実体の列（`columns` を持たなければ該当するテーブルの列）を返却する。"""
        if _items(entity, "columns"):
            return _er_entity_columns(entity)
        table = self.table(entity)
        return _er_table_columns(table) if table is not None else []


def _er_layout(tables: list[dict[str, Any]]) -> int:
    """テーブルを格子に配置し、図の幅を返却する。"""
    y = ER_LAYOUT["margin"]
    for start in range(0, len(tables), ER_LAYOUT["per_row"]):
        row = tables[start : start + ER_LAYOUT["per_row"]]
        for index, table in enumerate(row):
            table["x"] = ER_LAYOUT["margin"] + index * (ER_LAYOUT["width"] + ER_LAYOUT["gap_x"])
            table["y"] = y
            table["w"] = ER_LAYOUT["width"]
        tallest = max(
            ER_LAYOUT["head"] + len(table["columns"]) * ER_LAYOUT["row"] + ER_LAYOUT["frame"]
            for table in row
        )
        y += tallest + ER_LAYOUT["gap_y"]
    per_row = min(len(tables), ER_LAYOUT["per_row"])
    return (
        ER_LAYOUT["margin"] * 2
        + per_row * ER_LAYOUT["width"]
        + max(per_row - 1, 0) * ER_LAYOUT["gap_x"]
    )


def _er_relation(
    relation: Mapping[str, Any], columns: Mapping[str, set[str]]
) -> dict[str, Any] | None:
    """関連を ER 図の部品の関係にする（両端の列か多重度が図に出せなければ `None`）。"""
    source, target = str(relation["from"]), str(relation["to"])
    from_column, to_column = relation.get("from_column"), relation.get("to_column")
    from_card, to_card = relation.get("from_cardinality"), relation.get("to_cardinality")
    # 無い列・知らない多重度を指す関係は mdmark の図全体を警告にするため出さない
    if (
        from_column not in columns.get(source, set())
        or to_column not in columns.get(target, set())
        or from_card not in ER_CARDINALITIES
        or to_card not in ER_CARDINALITIES
    ):
        return None
    item: dict[str, Any] = {
        "from": source,
        "fromColumn": str(from_column),
        "fromCard": str(from_card),
        "to": target,
        "toColumn": str(to_column),
        "toCard": str(to_card),
    }
    if relation.get("label"):
        item["label"] = str(relation["label"])
    return item


def _er(
    value: Mapping[str, Any], head: DiagramHead, tables: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """mdmark の ER 図の部品の定義を組み立てる。"""
    model = _ErModel(value, tables)
    nodes: list[dict[str, Any]] = []
    for entity in model.entities:
        name = str(entity["name"])
        node: dict[str, Any] = {"id": name, "name": name, "label": name}
        table = model.table(entity)
        # テンプレートのテーブルに該当する: 物理名と概要を使用する
        if table is not None:
            node["name"] = str(table.get("name", name))
            if table.get("summary"):
                node["desc"] = str(table["summary"])
        node["columns"] = model.columns(entity)
        nodes.append(node)
    # 実体ごとの列の名前（関係の両端の列が実体にあるかを確認する）
    columns = {node["id"]: {str(column["name"]) for column in node["columns"]} for node in nodes}
    relations = [
        item
        for item in (_er_relation(relation, columns) for relation in _items(value, "relations"))
        if item is not None
    ]
    width = _er_layout(nodes)
    return {
        "title": head.title,
        "scope": head.scope,
        "updated": head.updated,
        "width": width,
        "tables": nodes,
        "relations": relations,
    }


def render_diagram(
    value: Mapping[str, Any],
    kind: DiagramKind,
    head: DiagramHead,
    *,
    tables: Sequence[Mapping[str, Any]] = (),
) -> str:
    """`x-diagram` の種類で、値から本文に配置する図のブロックを組み立てる。"""
    if kind == "state":
        return _block("flow", layout_flow(_state_graph(value), head))
    if kind in FLOW_KINDS:
        return _block("flow", layout_flow(_flow_graph(value, kind), head))
    if kind == "er":
        return _block("er", _er(value, head, tables))
    raise ValueError(f"x-diagram {kind} は描けません")


def render_mermaid(code: str, head: DiagramHead) -> str:
    """手で記載する Mermaid のコードを、読み取れれば mdmark の図の部品に、読み取れなければ Mermaid のまま組み立てる。"""
    graph = parse_mermaid(code)
    # 読み取れない: 元のコードのまま
    if graph is None:
        return f"```mermaid\n{code}\n```"
    # フローチャート: 配置してフロー図にする
    if isinstance(graph, FlowGraph):
        return _block("flow", layout_flow(graph, head))
    # シーケンス図: 相手とメッセージの定義にする
    steps: list[dict[str, Any]] = []
    for message in graph.messages:
        step: dict[str, Any] = {
            "from": message.source,
            "to": message.target,
            "label": message.label,
        }
        if message.reply:
            step["reply"] = True
        steps.append(step)
    definition = {
        "title": head.title,
        "scope": head.scope,
        "updated": head.updated,
        "participants": [
            {"id": participant.id, "kind": participant.kind, "name": participant.name}
            for participant in graph.participants
        ],
        "steps": steps,
    }
    return _block("sequence", definition)
