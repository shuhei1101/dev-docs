"""`x-diagram` の値と手で書く Mermaid の、mdmark の図の部品か Mermaid のコードブロックへの描画。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from dev_docs.features.convert.flow_layout import layout_flow
from dev_docs.features.convert.mermaid import parse_mermaid
from dev_docs.features.convert.types import (
    DiagramHead,
    DiagramKind,
    FlowEdge,
    FlowGraph,
    FlowNode,
    NodeKind,
)

INDENT = "  "
FLOW_KINDS = ("flowchart", "dataflow", "architecture", "state")
LEFT_TO_RIGHT_KINDS = ("dataflow", "architecture")
# `x-diagram` のノードの `kind`・`shape` から mdmark の箱の種類（どれにも当たらなければ `script`）
NODE_KINDS: dict[str, NodeKind] = {
    "actor": "external",
    "external": "external",
    "stadium": "external",
    "circle": "external",
    "store": "data",
    "cylinder": "data",
    "diamond": "dm",
}
PLAIN_NAME = re.compile(r"^[\w\-]+$")


def _text(value: Any) -> str:
    """ラベルの文字列にする（`"` は `#quot;` に替える）。"""
    return str(value).replace("\n", " ").replace('"', "#quot;")


def _items(value: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """値の配列のうち、辞書の要素だけを取り出す。"""
    items = value.get(key)
    return [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []


def _block(marker: str, definition: Mapping[str, Any]) -> str:
    """mdmark の図の部品の範囲に、定義の JSON のコードブロックを置く。"""
    code = json.dumps(definition, ensure_ascii=False, indent=2)
    return f"<!-- {marker} -->\n\n```json\n{code}\n```\n\n<!-- /{marker} -->"


def _node_kind(node: Mapping[str, Any]) -> NodeKind:
    """ノードの `kind` と `shape` から箱の種類を決める。"""
    for key in ("kind", "shape"):
        kind = NODE_KINDS.get(str(node.get(key)))
        if kind is not None:
            return kind
    return "script"


def _flow_graph(value: Mapping[str, Any], kind: DiagramKind) -> FlowGraph:
    """flow 系の値を中間データにする（`subgraphs`・`clicks` は描かない）。"""
    direction = value.get("direction")
    left_to_right = direction == "LR" or (direction is None and kind in LEFT_TO_RIGHT_KINDS)
    nodes = [
        FlowNode(id=str(node["id"]), name=str(node.get("label", node["id"])), kind=_node_kind(node))
        for node in _items(value, "nodes")
    ]
    known = {node.id for node in nodes}
    edges: list[FlowEdge] = []
    for edge in _items(value, "edges"):
        source, target = str(edge["from"]), str(edge["to"])
        # 宣言の無い端の箱: 名前を ID にして足す
        for end in (source, target):
            if end not in known:
                nodes.append(FlowNode(id=end, name=end, kind="script"))
                known.add(end)
        label = edge.get("label")
        edges.append(FlowEdge(source=source, target=target, label=str(label) if label else None))
    return FlowGraph(direction="LR" if left_to_right else "TD", nodes=nodes, edges=edges)


def _state_graph(value: Mapping[str, Any]) -> FlowGraph:
    """状態遷移の値を、状態を箱・遷移を線にした中間データにする。"""
    names: list[str] = [str(item["name"]) for item in _items(value, "states")]
    for transition in _items(value, "transitions"):
        for end in (transition.get("from"), transition.get("to")):
            if end is not None and str(end) not in names:
                names.append(str(end))
    initial = value.get("initial")
    final = value.get("final")
    finals = {str(name) for name in final} if isinstance(final, list) else set()
    ids = {name: f"s{index + 1}" for index, name in enumerate(names)}
    nodes = [
        FlowNode(
            id=ids[name],
            name=name,
            kind="script",
            sub="初期状態"
            if initial is not None and name == str(initial)
            else "終了状態"
            if name in finals
            else None,
        )
        for name in names
    ]
    edges: list[FlowEdge] = []
    for transition in _items(value, "transitions"):
        parts = [
            str(transition["trigger"]) if transition.get("trigger") else "",
            f"[{transition['condition']}]" if transition.get("condition") else "",
        ]
        label = " ".join(part for part in parts if part)
        edges.append(
            FlowEdge(
                source=ids[str(transition["from"])],
                target=ids[str(transition["to"])],
                label=label or None,
            )
        )
    return FlowGraph(direction="TD", nodes=nodes, edges=edges)


def _entity_name(name: Any) -> str:
    """ER 図の実体の名前（空白などを含むときは `"` で囲む）。"""
    text = str(name)
    return text if PLAIN_NAME.match(text) else f'"{_text(text)}"'


def _er(value: Mapping[str, Any]) -> str:
    """`erDiagram` の Mermaid を組み立てる。"""
    lines = ["erDiagram"]
    for entity in _items(value, "entities"):
        lines.append(f"{INDENT}{_entity_name(entity['name'])} {{")
        columns: Sequence[Any] = entity.get("columns") or []
        for column in columns:
            if not isinstance(column, Mapping):
                continue
            parts = [str(column.get("type", "string")).replace(" ", "_"), str(column["name"])]
            if column.get("key"):
                parts.append(str(column["key"]))
            if column.get("comment"):
                parts.append(f'"{_text(column["comment"])}"')
            lines.append(f"{INDENT * 2}{' '.join(parts)}")
        lines.append(f"{INDENT}}}")
    for relation in _items(value, "relations"):
        label = f'"{_text(relation["label"])}"' if relation.get("label") else '""'
        lines.append(
            f"{INDENT}{_entity_name(relation['from'])} {relation['cardinality']} "
            f"{_entity_name(relation['to'])} : {label}"
        )
    return "\n".join(lines)


def render_diagram(value: Mapping[str, Any], kind: DiagramKind, head: DiagramHead) -> str:
    """`x-diagram` の種類で、値から本文に置く図のブロックを組み立てる。"""
    if kind == "state":
        return _block("flow", layout_flow(_state_graph(value), head))
    if kind in FLOW_KINDS:
        return _block("flow", layout_flow(_flow_graph(value, kind), head))
    if kind == "er":
        return f"```mermaid\n{_er(value)}\n```"
    raise ValueError(f"x-diagram {kind} は描けません")


def render_mermaid(code: str, head: DiagramHead) -> str:
    """手で書く Mermaid のコードを、読み取れれば mdmark の図の部品に、読み取れなければ Mermaid のまま組み立てる。"""
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
