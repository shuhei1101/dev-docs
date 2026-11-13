"""手で記載する Mermaid の `flowchart`・`sequenceDiagram` の読み取り。"""

from __future__ import annotations

import re

from dev_docs.features.convert.types import (
    FlowEdge,
    FlowGraph,
    FlowNode,
    NodeKind,
    SequenceGraph,
    SequenceMessage,
    SequenceParticipant,
)

FLOW_HEADER = re.compile(r"^(flowchart|graph)(\s+(TD|TB|LR))?$")
# ノードの括弧と mdmark のノードの種類（長い括弧から照らす）
NODE_SHAPES: tuple[tuple[str, str, NodeKind], ...] = (
    ("[(", ")]", "data"),
    ("([", "])", "external"),
    ("((", "))", "external"),
    ("[[", "]]", "script"),
    ("{{", "}}", "script"),
    ("[", "]", "script"),
    ("(", ")", "script"),
    ("{", "}", "dm"),
)
FLOW_ARROWS = ("-.->", "==>", "-->", "---")
SEQUENCE_ARROWS = ("-->>", "->>", "--x", "-x", "--)", "-)", "-->", "->")
# `-` は単語の間にだけ配置できる（`a-->b` の `a` を `a--` と読み取らない）
ID = r"\w+(?:-\w+)*"
NODE_ID = re.compile(ID)
FLOW_ARROW = re.compile(
    r"\s*(?:--\s*(?P<text>[^->|][^>|]*?)\s*(?:-->|---)|(?:-\.->|==>|-->|---)(?:\|(?P<pipe>[^|]*)\|)?)\s*"
)
PARTICIPANT = re.compile(rf"^(participant|actor)\s+({ID})(?:\s+as\s+(.+))?$")
MESSAGE = re.compile(
    rf"^({ID})\s*("
    + "|".join(re.escape(arrow) for arrow in SEQUENCE_ARROWS)
    + rf")\s*[+\-]?({ID})\s*(?::\s*(.*))?$"
)


def _label(text: str) -> str:
    """ラベルの `"` の囲みを除去し、`<br>` を空白にする。"""
    text = text.strip()
    if len(text) > 1 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return re.sub(r"<br\s*/?>", " ", text).strip()


def _read_node(text: str, position: int) -> tuple[str, str | None, NodeKind, int] | None:
    """`position` からノードの `id` と括弧のラベルを読み取り、`id`・ラベル・種類・読み取りを終えた位置を返却する。"""
    match = NODE_ID.match(text, position)
    if match is None:
        return None
    node_id, end = match.group(0), match.end()
    for opening, closing, kind in NODE_SHAPES:
        if text.startswith(opening, end):
            close = text.find(closing, end + len(opening))
            if close < 0:
                return None
            return node_id, _label(text[end + len(opening) : close]), kind, close + len(closing)
    return node_id, None, "script", end


def _parse_flow_line(line: str, nodes: dict[str, FlowNode], edges: list[FlowEdge]) -> bool:
    """フローチャートの 1 行を、ノードの宣言とノードをつなぐ線の連なりとして読み取る。"""
    found: list[tuple[str, str | None]] = []
    position = 0
    while True:
        node = _read_node(line, position)
        if node is None:
            return False
        node_id, label, kind, position = node
        if node_id not in nodes or (label is not None and nodes[node_id].name == node_id):
            nodes[node_id] = FlowNode(id=node_id, name=label or node_id, kind=kind)
        if found:
            edges.append(FlowEdge(source=found[-1][0], target=node_id, label=found[-1][1]))
        if position == len(line):
            return True
        arrow = FLOW_ARROW.match(line, position)
        if arrow is None:
            return False
        text = arrow.group("text") or arrow.group("pipe")
        found.append((node_id, _label(text) if text else None))
        position = arrow.end()


def _parse_flow(header: re.Match[str], lines: list[str]) -> FlowGraph | None:
    """フローチャートの行を中間データにする。"""
    nodes: dict[str, FlowNode] = {}
    edges: list[FlowEdge] = []
    for line in lines:
        # ノードの宣言でも線でもない行（subgraph・style など）: 図ごと読み取らない
        if not _parse_flow_line(line, nodes, edges):
            return None
    if not nodes:
        return None
    return FlowGraph(
        direction="LR" if header.group(3) == "LR" else "TD", nodes=list(nodes.values()), edges=edges
    )


def _parse_sequence(lines: list[str]) -> SequenceGraph | None:
    """シーケンス図の行を中間データにする。"""
    participants: dict[str, SequenceParticipant] = {}
    messages: list[SequenceMessage] = []

    def add(participant_id: str) -> None:
        if participant_id not in participants:
            participants[participant_id] = SequenceParticipant(
                id=participant_id, name=participant_id, kind="script"
            )

    for line in lines:
        if line == "autonumber":
            continue
        declared = PARTICIPANT.match(line)
        # 相手の宣言: actor は外部のシステムのノードにする
        if declared:
            kind, participant_id, name = declared.groups()
            participants[participant_id] = SequenceParticipant(
                id=participant_id,
                name=_label(name) if name else participant_id,
                kind="external" if kind == "actor" else "script",
            )
            continue
        message = MESSAGE.match(line)
        # 相手の宣言でもメッセージでもない行（Note・alt・loop など）: 図ごと読み取らない
        if message is None:
            return None
        source, arrow, target, label = message.groups()
        add(source)
        add(target)
        messages.append(
            SequenceMessage(
                source=source,
                target=target,
                label=_label(label or ""),
                reply=arrow.startswith("--"),
            )
        )
    if not messages:
        return None
    return SequenceGraph(participants=list(participants.values()), messages=messages)


def parse_mermaid(code: str) -> FlowGraph | SequenceGraph | None:
    """Mermaid のコードを、フロー図かシーケンス図の中間データにする。"""
    lines = [
        line.strip()
        for line in code.splitlines()
        if line.strip() and not line.strip().startswith("%%")
    ]
    if not lines:
        return None
    header = FLOW_HEADER.match(lines[0])
    if header:
        return _parse_flow(header, lines[1:])
    if lines[0] == "sequenceDiagram":
        return _parse_sequence(lines[1:])
    return None
