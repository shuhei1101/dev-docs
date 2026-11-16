"""`x-diagram` の値と手で記載する Mermaid の、mdmark の map の範囲か Mermaid のコードブロックへの描画。"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from dev_docs.features.convert.types import DiagramHead, DiagramKind

FLOW_KINDS = ("flowchart", "dataflow", "architecture")
LEFT_TO_RIGHT_KINDS = ("dataflow", "architecture")
# `x-diagram` のノードの `kind` から Mermaid のクラス（画面の map の設定の `map.kinds` のキー）
NODE_KINDS = {
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
# 辺の `line` に記載できる線の種類。`flow` 以外は補足の `layout` の `line` に入れる
LINE_KINDS = ("flow", "read", "write", "reply", "loop")
# `line` が無い辺と、`LINE_KINDS` に無い `line` の辺の種類
DEFAULT_LINE = "flow"
# 遷移の `from` のこの値は、`representative` の状態から線を描く
ALL_STATES = "全状態"
# 遷移の `to` のこの値は、`representative` の状態へ線を描く
PREVIOUS_STATE = "元の状態"
# 関連の `from_cardinality`・`to_cardinality` から Mermaid の関連の左側・右側の記号
ER_FROM_MARKS = {"1": "||", "0..1": "|o", "1..n": "}|", "0..n": "}o"}
ER_TO_MARKS = {"1": "||", "0..1": "o|", "1..n": "|{", "0..n": "o{"}
# 実体の列の `key` のうち、Mermaid の列のキーにする値
ER_COLUMN_KEYS = ("PK", "FK", "UK")
# テンプレートのテーブルの列のフラグから Mermaid の列のキー
ER_TABLE_KEYS = (("primary_key", "PK"), ("foreign_key", "FK"))
# `type` を持たない列の Mermaid の型（Mermaid の列の行は型を省けない）
ER_DEFAULT_TYPE = "any"
# 手で記載する Mermaid のうち、map の範囲に入れる 1 行目の最初の単語
MAP_MERMAID_KINDS = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "erDiagram",
    "stateDiagram-v2",
    "stateDiagram",
)
MAP_DATA_VERSION = 1
# そのまま Mermaid の `flowchart` のノードの ID にできる ID
MERMAID_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")
# ID にできない `flowchart` の予約語と枠の ID（大文字と小文字を区別しない）
MERMAID_RESERVED_IDS = frozenset(
    {
        "end",
        "subgraph",
        "graph",
        "flowchart",
        "direction",
        "click",
        "class",
        "classdef",
        "style",
        "linkstyle",
        "frame",
    }
)
# `clicks` の `href` と手で書くフローチャートの `click` の行の、`{文書の ID}#{項目のパス}` を指すリンク先の接頭辞
ID_LINK_PREFIX = "id:"
# 手で書く Mermaid のうち、`click` の行のリンク先を書き換える 1 行目の最初の単語
FLOWCHART_MERMAID_KINDS = ("flowchart", "graph")
# 手で書くフローチャートの `click {ノード} "id:…"`・`click {ノード} href "id:…"` の行
MERMAID_ID_CLICK = re.compile(
    r'^(?P<head>[ \t]*click[ \t]+\S+[ \t]+(?:href[ \t]+)?)"id:(?P<target>[^"]*)"(?P<tail>[^\n]*)$',
    re.M,
)


def _items(value: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """値の配列のうち、辞書の要素だけを取り出す。"""
    items = value.get(key)
    return [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []


def _quote(text: Any) -> str:
    """Mermaid の文字列を閉じる `"` を `#quot;` にする。"""
    return str(text).replace('"', "#quot;")


def _comment_safe(value: Any) -> Any:
    """マーカーの JSON の文字の値とキーの `--` を `- -` にする（HTML のコメントを閉じないため）。"""
    if isinstance(value, str):
        # `---` は 1 回の置き換えで `- --` になるため、無くなるまで置き換える
        while "--" in value:
            value = value.replace("--", "- -")
        return value
    if isinstance(value, Mapping):
        return {_comment_safe(key): _comment_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_comment_safe(item) for item in value]
    return value


def _marker(name: str, value: Mapping[str, Any]) -> str:
    """`<!-- {name}: {JSON} -->` のマーカーを組み立てる。"""
    return f"<!-- {name}: {json.dumps(_comment_safe(value), ensure_ascii=False)} -->"


class _MapData:
    """map の補足の `notes`・`layout`。"""

    def __init__(self) -> None:
        self.notes: dict[str, dict[str, str]] = {}
        self.layout: dict[str, dict[str, str]] = {}

    def note(self, key: str, text: Any) -> None:
        """値があれば、`key` のツールチップに出す説明を入れる。"""
        if text:
            self.notes[key] = {"text": str(text)}

    def marker(self) -> str | None:
        """補足のマーカー（`notes`・`layout` がどちらも空なら `None`）。"""
        if not self.notes and not self.layout:
            return None
        data: dict[str, Any] = {"version": MAP_DATA_VERSION}
        if self.notes:
            data["notes"] = self.notes
        if self.layout:
            data["layout"] = self.layout
        return _marker("map-data", data)


def _map_block(code: str, head: DiagramHead, data: _MapData | None = None) -> str:
    """Mermaid のコードを map の範囲で囲み、補足があればコードブロックの後に配置する。"""
    parts = [_marker("map", {"title": head.title}), f"```mermaid\n{code}\n```"]
    extra = data.marker() if data is not None else None
    if extra is not None:
        parts.append(extra)
    parts.append("<!-- /map -->")
    return "\n\n".join(parts)


def _node_class(node: Mapping[str, Any]) -> str:
    """ノードの `kind` から Mermaid のクラスを決める。"""
    return NODE_KINDS.get(str(node.get("kind", DEFAULT_NODE_KIND)), NODE_KINDS[DEFAULT_NODE_KIND])


class _NodeIds:
    """`x-diagram` のノードの ID から Mermaid のノードの ID を引く。"""

    def __init__(self, used: set[str]) -> None:
        self.used = used
        self.ids: dict[str, str] = {}
        self.count = 0

    def get(self, original: str) -> str:
        """ID にできればそのまま、できなければ使用されていない `n{番号}` にする。"""
        if original not in self.ids:
            if MERMAID_SAFE_ID.match(original) and original.lower() not in MERMAID_RESERVED_IDS:
                self.ids[original] = original
            else:
                self.count += 1
                while f"n{self.count}" in self.used:
                    self.count += 1
                self.ids[original] = f"n{self.count}"
        return self.ids[original]


def _link_href(href: str) -> str:
    """リンク先の `"` を `%22` にする（Mermaid の文字列を閉じないため）。"""
    return href.replace('"', "%22")


def _click_lines(
    value: Mapping[str, Any],
    ids: _NodeIds,
    drawn: Mapping[str, str],
    link: Callable[[str], str | None],
) -> list[str]:
    """`clicks` のうち、図にあるノードを指し、リンク先が決まる要素を `click` の行にする。"""
    lines: list[str] = []
    for click in _items(value, "clicks"):
        original = str(click.get("id", ""))
        # 図に無いノード: `click` のためだけにノードを増やさない
        if original not in ids.ids or ids.ids[original] not in drawn:
            continue
        href = str(click.get("href", ""))
        target = link(href[len(ID_LINK_PREFIX) :]) if href.startswith(ID_LINK_PREFIX) else href
        if target is None:
            continue
        lines.append(f'{ids.ids[original]} "{_link_href(target)}"')
    return [f"click {line}" for line in lines]


def _flowchart(
    value: Mapping[str, Any], kind: DiagramKind, link: Callable[[str], str | None]
) -> tuple[list[str], _MapData]:
    """flow 系の値を `flowchart` の行と補足にする。"""
    # 向き: 指定があればその値、無ければ図の種類の既定
    direction = (
        value["direction"]
        if value.get("direction") in ("TD", "LR")
        else "LR"
        if kind in LEFT_TO_RIGHT_KINDS
        else "TD"
    )
    data = _MapData()
    nodes, edges = _items(value, "nodes"), _items(value, "edges")
    ids = _NodeIds(
        {str(node["id"]) for node in nodes}
        | {str(edge[end]) for edge in edges for end in ("from", "to")}
    )
    # Mermaid のノードの ID からノードの行（出た順）
    node_lines: dict[str, str] = {}
    for node in nodes:
        node_id = ids.get(str(node["id"]))
        label = _quote(node.get("label", node["id"]))
        node_lines[node_id] = f'{node_id}["{label}"]:::{_node_class(node)}'
        data.note(node_id, node.get("hint"))
    edge_lines: list[str] = []
    for edge in edges:
        source, target = ids.get(str(edge["from"])), ids.get(str(edge["to"]))
        # 宣言の無い端のノード: 名前をラベルにして追加する
        for end, name in ((source, edge["from"]), (target, edge["to"])):
            if end not in node_lines:
                node_lines[end] = f'{end}["{_quote(name)}"]:::{NODE_KINDS[DEFAULT_NODE_KIND]}'
        edge_label = edge.get("label")
        arrow = f'-->|"{_quote(edge_label)}"|' if edge_label else "-->"
        edge_lines.append(f"{source} {arrow} {target}")
        edge_id = f"{source}->{target}"
        data.note(edge_id, edge.get("tip"))
        line = edge.get("line")
        # `flow` 以外の知っている線の種類: 補足の `layout` に入れる（知らない値は `flow` として扱う）
        if line in LINE_KINDS and line != DEFAULT_LINE:
            data.layout[edge_id] = {"line": str(line)}
    lines = [f"flowchart {direction}"]
    frame = value.get("frame")
    framed: list[str] = []
    # 枠がある: 枠のノードの行を `subgraph` で囲む
    if isinstance(frame, Mapping):
        framed = [
            ids.get(str(node_id))
            for node_id in frame.get("nodes") or []
            if ids.get(str(node_id)) in node_lines
        ]
        lines.append(f'  subgraph frame ["{_quote(frame.get("label", ""))}"]')
        lines += [f"    {node_lines[node_id]}" for node_id in framed]
        lines.append("  end")
    lines += [f"  {line}" for node_id, line in node_lines.items() if node_id not in framed]
    lines += [f"  {line}" for line in edge_lines]
    lines += [f"  {line}" for line in _click_lines(value, ids, node_lines, link)]
    return lines, data


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


def _state(value: Mapping[str, Any]) -> list[str]:
    """状態遷移の値を `stateDiagram-v2` の行にする。"""
    transitions = _items(value, "transitions")
    names: list[str] = [str(item["name"]) for item in _items(value, "states")]
    # 遷移の端に出た `states` に無い状態も追加する
    for transition in transitions:
        for end in _state_ends(transition):
            if end and end not in names:
                names.append(end)
    ids = {name: f"s{index + 1}" for index, name in enumerate(names)}
    lines = ["stateDiagram-v2"]
    lines += [f'  state "{_quote(name)}" as {ids[name]}' for name in names]
    initial = value.get("initial")
    if initial is not None and str(initial) in ids:
        lines.append(f"  [*] --> {ids[str(initial)]}")
    for transition in transitions:
        source, target = _state_ends(transition)
        # `representative` が無く端が決まらない遷移: 線を描かない（図の元データの表に残る）
        if source not in ids or target not in ids:
            continue
        label = _state_label(transition)
        lines.append(f"  {ids[source]} --> {ids[target]}" + (f" : {label}" if label else ""))
    final = value.get("final")
    if isinstance(final, list):
        lines += [f"  {ids[str(name)]} --> [*]" for name in final if str(name) in ids]
    return lines


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


def _er_columns(
    entity: Mapping[str, Any], by_title: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, str]]:
    """実体の列（`columns` を持たなければ論理名が実体の名前のテーブルの列）を、型・名前・キー・説明にする。"""
    # 実体が列を持つ: その列の `key` を使用する
    if _items(entity, "columns"):
        columns: list[dict[str, str]] = []
        for column in _items(entity, "columns"):
            key = str(column.get("key", ""))
            columns.append(
                {
                    "type": str(column.get("type") or ER_DEFAULT_TYPE),
                    "name": str(column["name"]),
                    "key": key if key in ER_COLUMN_KEYS else "",
                    "note": str(column.get("comment") or ""),
                }
            )
        return columns
    # 列を持たない: テンプレートのテーブルの列のフラグをキーにする
    table = by_title.get(str(entity.get("name")))
    return [
        {
            "type": str(column.get("type") or ER_DEFAULT_TYPE),
            "name": str(column["name"]),
            "key": ", ".join(mark for flag, mark in ER_TABLE_KEYS if column.get(flag)),
            "note": str(column.get("comment") or column.get("title") or ""),
        }
        for column in (_items(table, "columns") if table is not None else [])
    ]


def _er_relations(
    value: Mapping[str, Any], entities: Mapping[str, list[dict[str, str]]]
) -> tuple[list[str], dict[tuple[str, str], str]]:
    """描ける関連の行と、先の列に付ける `参照:` のコメントを組み立てる。"""
    lines: list[str] = []
    references: dict[tuple[str, str], str] = {}
    for relation in _items(value, "relations"):
        source, target = str(relation.get("from")), str(relation.get("to"))
        from_column, to_column = relation.get("from_column"), relation.get("to_column")
        from_mark = ER_FROM_MARKS.get(str(relation.get("from_cardinality")))
        to_mark = ER_TO_MARKS.get(str(relation.get("to_cardinality")))
        # 無い列・知らない多重度を指す関連: 描かない（図の元データの表に残る）
        if (
            from_mark is None
            or to_mark is None
            or from_column not in {column["name"] for column in entities.get(source, [])}
            or to_column not in {column["name"] for column in entities.get(target, [])}
        ):
            continue
        label = _quote(relation.get("label", ""))
        lines.append(f'  {source} {from_mark}--{to_mark} {target} : "{label}"')
        # mdmark は関連の端の列を、このコメントを持つ FK の列から選ぶ
        references[(target, str(to_column))] = f"参照: {source}.{from_column}"
    return lines, references


def _er(
    value: Mapping[str, Any], tables: Sequence[Mapping[str, Any]]
) -> tuple[list[str], _MapData]:
    """ER 図の値を `erDiagram` の行と補足にする。"""
    by_title = {str(table.get("title")): table for table in tables}
    entities = {
        str(entity["name"]): _er_columns(entity, by_title) for entity in _items(value, "entities")
    }
    relation_lines, references = _er_relations(value, entities)
    data = _MapData()
    lines = ["erDiagram"]
    for name, columns in entities.items():
        lines.append(f"  {name} {{")
        for column in columns:
            row = f"{column['type']} {column['name']}"
            if column["key"]:
                row += f" {column['key']}"
            reference = references.get((name, column["name"]))
            if reference is not None:
                row += f' "{_quote(reference)}"'
            lines.append(f"    {row}")
            data.note(f"{name}.{column['name']}", column["note"])
        lines.append("  }")
    return lines + relation_lines, data


def render_diagram(
    value: Mapping[str, Any],
    kind: DiagramKind,
    head: DiagramHead,
    *,
    tables: Sequence[Mapping[str, Any]] = (),
    link: Callable[[str], str | None],
) -> str:
    """`x-diagram` の種類で、値から本文に配置する map の範囲を組み立てる。"""
    if kind in FLOW_KINDS:
        lines, data = _flowchart(value, kind, link)
        return _map_block("\n".join(lines), head, data)
    if kind == "state":
        return _map_block("\n".join(_state(value)), head)
    if kind == "er":
        lines, data = _er(value, tables)
        return _map_block("\n".join(lines), head, data)
    raise ValueError(f"x-diagram {kind} は描けません")


def _link_clicks(code: str, link: Callable[[str], str | None]) -> str:
    """フローチャートの `click` の行の `id:` のリンク先を引いた値にし、引けない行を消す。"""

    def replace(match: re.Match[str]) -> str:
        target = link(match.group("target"))
        if target is None:
            return ""
        return f'{match.group("head")}"{_link_href(target)}"{match.group("tail")}'

    rewritten = MERMAID_ID_CLICK.sub(replace, code)
    # 消した `click` の行の空行を詰める（元から空の行は残す）
    original_lines = code.splitlines()
    return "\n".join(
        line
        for line, before in zip(rewritten.splitlines(), original_lines, strict=True)
        if line or not MERMAID_ID_CLICK.match(before)
    )


def render_mermaid(code: str, head: DiagramHead, link: Callable[[str], str | None]) -> str:
    """手で記載する Mermaid のコードを、map で描ける種類なら map の範囲に、それ以外は Mermaid のまま組み立てる。"""
    first = next((line.split()[0] for line in code.splitlines() if line.strip()), "")
    # map で描ける種類: フローチャートは click の id のリンク先を書き換えて、map の範囲で囲む
    if first in MAP_MERMAID_KINDS:
        if first in FLOWCHART_MERMAID_KINDS:
            code = _link_clicks(code, link)
        return _map_block(code, head)
    return f"```mermaid\n{code}\n```"
