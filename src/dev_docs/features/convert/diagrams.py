"""`x-diagram` の Mermaid の組み立て。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from dev_docs.features.convert.types import DiagramKind

INDENT = "  "
FLOW_KINDS = ("flowchart", "dataflow", "architecture")
SHAPE_BRACKETS = {
    "rect": ("[", "]"),
    "round": ("(", ")"),
    "stadium": ("([", "])"),
    "diamond": ("{", "}"),
    "circle": ("((", "))"),
    "cylinder": ("[(", ")]"),
    "hexagon": ("{{", "}}"),
    "subroutine": ("[[", "]]"),
}
KIND_SHAPES = {
    "actor": "stadium",
    "process": "round",
    "store": "cylinder",
    "system": "rect",
    "external": "subroutine",
}
EDGE_ARROWS = {"solid": "-->", "dotted": "-.->", "thick": "==>", "open": "---"}
NEEDS_QUOTE = re.compile(r"[()\[\]{}|\"<>;#&]")
PLAIN_NAME = re.compile(r"^[\w\-]+$")


def _text(value: Any) -> str:
    """ラベルの文字列にする（`"` は `#quot;` に替える）。"""
    return str(value).replace("\n", " ").replace('"', "#quot;")


def _label(value: Any) -> str:
    """ラベルに記号があるときだけ `"` で囲む。"""
    text = _text(value)
    return f'"{text}"' if NEEDS_QUOTE.search(text) or "#quot;" in text else text


def _items(value: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """値の配列のうち、辞書の要素だけを取り出す。"""
    items = value.get(key)
    return [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []


def _flowchart(value: Mapping[str, Any], kind: str) -> str:
    """`flowchart` の Mermaid を組み立てる。"""
    direction = value.get("direction") or ("TD" if kind == "flowchart" else "LR")
    lines = [f"flowchart {direction}"]
    for node in _items(value, "nodes"):
        shape = node.get("shape") or KIND_SHAPES.get(str(node.get("kind")), "rect")
        opening, closing = SHAPE_BRACKETS.get(str(shape), SHAPE_BRACKETS["rect"])
        lines.append(
            f"{INDENT}{node['id']}{opening}{_label(node.get('label', node['id']))}{closing}"
        )
    for edge in _items(value, "edges"):
        arrow = EDGE_ARROWS.get(str(edge.get("line") or "solid"), "-->")
        label = f"|{_text(edge['label'])}|" if edge.get("label") else ""
        lines.append(f"{INDENT}{edge['from']} {arrow}{label} {edge['to']}")
    for group in _items(value, "subgraphs"):
        title = _label(group.get("label", group["id"]))
        lines.append(f"{INDENT}subgraph {group['id']}[{title}]")
        lines.extend(f"{INDENT * 2}{node_id}" for node_id in group.get("nodes", []))
        lines.append(f"{INDENT}end")
    for click in _items(value, "clicks"):
        lines.append(f'{INDENT}click {click["id"]} href "{click["href"]}"')
    return "\n".join(lines)


def _state(value: Mapping[str, Any]) -> str:
    """`stateDiagram-v2` の Mermaid を組み立てる。"""
    names: list[str] = []
    for item in _items(value, "states"):
        names.append(str(item["name"]))
    for transition in _items(value, "transitions"):
        for end in (transition.get("from"), transition.get("to")):
            if end is not None and str(end) not in names:
                names.append(str(end))
    ids: dict[str, str] = {}
    lines = ["stateDiagram-v2"]
    for index, name in enumerate(names):
        if PLAIN_NAME.match(name):
            ids[name] = name
        else:
            ids[name] = f"s{index}"
            lines.append(f'{INDENT}state "{_text(name)}" as s{index}')
    initial = value.get("initial")
    if initial is not None:
        lines.append(f"{INDENT}[*] --> {ids.get(str(initial), initial)}")
    for transition in _items(value, "transitions"):
        label = " ".join(
            part
            for part in (
                _text(transition["trigger"]) if transition.get("trigger") else "",
                f"[{_text(transition['condition'])}]" if transition.get("condition") else "",
            )
            if part
        )
        suffix = f" : {label}" if label else ""
        source, target = str(transition["from"]), str(transition["to"])
        lines.append(f"{INDENT}{ids[source]} --> {ids[target]}{suffix}")
    final = value.get("final")
    for name in final if isinstance(final, list) else []:
        lines.append(f"{INDENT}{ids.get(str(name), name)} --> [*]")
    return "\n".join(lines)


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


def render_diagram(value: Mapping[str, Any], kind: DiagramKind) -> str:
    """`x-diagram` の種類で、値から Mermaid の図を組み立てる。"""
    if kind in FLOW_KINDS:
        return _flowchart(value, kind)
    if kind == "state":
        return _state(value)
    if kind == "er":
        return _er(value)
    raise ValueError(f"x-diagram {kind} は描けません")
