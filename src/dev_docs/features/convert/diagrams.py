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
# Mermaid の多重度の片端の記号から、mdmark の ER 図の部品の多重度
ER_CARDINALITIES = {
    "||": "1",
    "|o": "0..1",
    "o|": "0..1",
    "|{": "1..n",
    "}|": "1..n",
    "o{": "0..n",
    "}o": "0..n",
}
# Mermaid の多重度（`{左}--{右}` か `{左}..{右}`）
ER_CARDINALITY = re.compile(r"^(?P<left>\S{2})(?:--|\.\.)(?P<right>\S{2})$")
# 実体の列の `key` から、mdmark の ER 図の部品の列のマーカー
ER_COLUMN_KEYS = {"PK": "pk", "FK": "fk"}
# `key: FK` の実体の列の `comment` から、指す実体と列
ER_FOREIGN_KEY_COMMENT = re.compile(r"^参照: (?P<entity>.+)\.(?P<column>[^.\s]+)$")
# ER 図のテーブルを格子に置く寸法（px）。`head`・`row`・`frame` は mdmark の ER 図の寸法と同じ値
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
    """同じ文書の `tables[]` から、テーブルの物理名と論理名のどちらからも論理名を引く表を作る。"""
    titles: dict[str, str] = {}
    for table in tables:
        # 論理名を持たないテーブルは、当てる見出し・実体が無いため入れない
        if table.get("title") is None:
            continue
        for key in ("name", "title"):
            if table.get(key) is not None:
                # 重なるキーは先に出たテーブルを残す
                titles.setdefault(str(table[key]), str(table["title"]))
    return titles


class _ErModel:
    """ER 図の実体ごとのテーブルと、外部キーが指す実体と列の引き方。"""

    def __init__(
        self,
        value: Mapping[str, Any],
        tables: Sequence[Mapping[str, Any]],
        classification: str | None,
    ) -> None:
        self.classification = classification
        self.by_title = {str(table.get("title")): table for table in tables}
        # 外部キーのテーブル名は物理名・論理名のどちらでも引く
        self.entity_of = er_table_titles(tables)
        self.entities = _items(value, "entities")

    def table(self, entity: Mapping[str, Any]) -> Mapping[str, Any] | None:
        """実体の `name` が `title` に当たるテーブルを返す。"""
        return self.by_title.get(str(entity.get("name")))

    def columns(self, entity: Mapping[str, Any]) -> list[dict[str, Any]]:
        """実体の列（`columns` を持たなければ当たるテーブルの列）を返す。"""
        if _items(entity, "columns"):
            return _er_entity_columns(entity)
        table = self.table(entity)
        return _er_table_columns(table) if table is not None else []

    def references(self, entity: Mapping[str, Any]) -> list[tuple[str, str, str]]:
        """実体の列のうち外部キーの列ごとに（列, 指す実体, 指す列）を返す。"""
        found: list[tuple[str, str, str]] = []
        for column in _items(entity, "columns"):
            matched = ER_FOREIGN_KEY_COMMENT.match(str(column.get("comment", "")))
            if column.get("key") == "FK" and matched:
                found.append((str(column["name"]), matched["entity"], matched["column"]))
        table = self.table(entity)
        if _items(entity, "columns") or table is None:
            return found
        for column in _items(table, "columns"):
            foreign_key = column.get("foreign_key")
            if not isinstance(foreign_key, Mapping) or not foreign_key.get("table"):
                continue
            target = self._foreign_key_target(str(foreign_key["table"]))
            if target is not None:
                found.append((str(column["name"]), *target))
        return found

    def _foreign_key_target(self, reference: str) -> tuple[str, str] | None:
        """`{分類}/{テーブル名}.{列}` から、同じ文書の（指す実体, 指す列）を返す。"""
        table_name, _, column = reference.rpartition(".")
        classification, _, name = table_name.rpartition("/")
        # 他の分類のテーブル: 同じ文書に無いので当てない
        if classification and classification != self.classification:
            return None
        entity = self.entity_of.get(name)
        return (entity, column) if entity is not None else None

    def ends(self, source: str, target: str) -> tuple[str, str] | None:
        """関連の元と先の実体から、（元の列, 先の列）を外部キーで決める（決まらなければ `None`）。"""
        by_name = {str(entity["name"]): entity for entity in self.entities}
        # 先の実体の外部キーが元の実体を指す
        for column, entity, referenced in self.references(by_name.get(target, {})):
            if entity == source:
                return referenced, column
        # 元の実体の外部キーが先の実体を指す
        for column, entity, referenced in self.references(by_name.get(source, {})):
            if entity == target:
                return column, referenced
        return None


def _er_cards(cardinality: str) -> tuple[str, str] | None:
    """Mermaid の多重度を、両端の多重度にする（読み替えられなければ `None`）。"""
    matched = ER_CARDINALITY.match(cardinality)
    if matched is None:
        return None
    left = ER_CARDINALITIES.get(matched["left"])
    right = ER_CARDINALITIES.get(matched["right"])
    return (left, right) if left is not None and right is not None else None


def _er_layout(tables: list[dict[str, Any]]) -> int:
    """テーブルを格子に置き、図の幅を返す。"""
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


def _er(
    value: Mapping[str, Any],
    head: DiagramHead,
    tables: Sequence[Mapping[str, Any]],
    classification: str | None,
) -> dict[str, Any]:
    """mdmark の ER 図の部品の定義を組み立てる。"""
    model = _ErModel(value, tables, classification)
    nodes: list[dict[str, Any]] = []
    for entity in model.entities:
        name = str(entity["name"])
        node: dict[str, Any] = {"id": name, "name": name, "label": name}
        table = model.table(entity)
        # テンプレートのテーブルに当たる: 物理名と概要を使う
        if table is not None:
            node["name"] = str(table.get("name", name))
            if table.get("summary"):
                node["desc"] = str(table["summary"])
        node["columns"] = model.columns(entity)
        nodes.append(node)
    relations: list[dict[str, Any]] = []
    for relation in _items(value, "relations"):
        source, target = str(relation["from"]), str(relation["to"])
        cards = _er_cards(str(relation.get("cardinality", "")))
        ends = model.ends(source, target)
        # 多重度を読み替えられない・端の列が決まらない関連は図に出さない（元データの表に残る）
        if cards is None or ends is None:
            continue
        item: dict[str, Any] = {
            "from": source,
            "fromColumn": ends[0],
            "fromCard": cards[0],
            "to": target,
            "toColumn": ends[1],
            "toCard": cards[1],
        }
        if relation.get("label"):
            item["label"] = str(relation["label"])
        relations.append(item)
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
    classification: str | None = None,
) -> str:
    """`x-diagram` の種類で、値から本文に置く図のブロックを組み立てる。"""
    if kind == "state":
        return _block("flow", layout_flow(_state_graph(value), head))
    if kind in FLOW_KINDS:
        return _block("flow", layout_flow(_flow_graph(value, kind), head))
    if kind == "er":
        return _block("er", _er(value, head, tables, classification))
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
