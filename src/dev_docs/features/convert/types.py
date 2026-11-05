"""変換の結果・図の中間データ・描画の文脈の型。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

type Shape = Literal["body", "table", "sections", "list", "diagram", "attributes"]
type DiagramKind = Literal["flowchart", "dataflow", "architecture", "state", "er"]
type NodeKind = Literal["llm", "dm", "script", "mcp", "data", "external"]


@dataclass(frozen=True)
class ConvertFailure:
    """本文の場所にエラーの囲みで出す、変換できなかった理由。"""

    reason: Literal["timeout", "exit", "not_runnable", "invalid_yaml"]
    kind: str
    detail: str
    script: str | None = None
    file: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class Converted:
    """画面に渡す Markdown か、変換の失敗。"""

    markdown: str
    table_keys: list[str] = field(default_factory=list)
    failure: ConvertFailure | None = None


@dataclass(frozen=True)
class DiagramHead:
    """mdmark の図の部品の定義に入れる題名・範囲・更新日。"""

    title: str
    scope: str
    updated: str


@dataclass(frozen=True)
class FlowNode:
    """配置の前のフロー図の箱。"""

    id: str
    name: str
    kind: NodeKind
    sub: str | None = None


@dataclass(frozen=True)
class FlowEdge:
    """配置の前のフロー図の線。"""

    source: str
    target: str
    label: str | None = None


@dataclass(frozen=True)
class FlowGraph:
    """`x-diagram` の値か手で書く Mermaid の `flowchart` から作る、配置の前のフロー図。"""

    direction: Literal["TD", "LR"]
    nodes: list[FlowNode]
    edges: list[FlowEdge]


@dataclass(frozen=True)
class SequenceParticipant:
    """シーケンス図の相手 1 つ。"""

    id: str
    name: str
    kind: Literal["script", "external"]


@dataclass(frozen=True)
class SequenceMessage:
    """シーケンス図のメッセージ 1 つ。"""

    source: str
    target: str
    label: str
    reply: bool


@dataclass(frozen=True)
class SequenceGraph:
    """手で書く Mermaid の `sequenceDiagram` から作るシーケンス図。"""

    participants: list[SequenceParticipant]
    messages: list[SequenceMessage]


@dataclass(frozen=True)
class DocumentLink:
    """本文の参照から張る、同じ配信元の文書へのリンク。"""

    title: str
    path: str


@dataclass(frozen=True)
class RenderContext:
    """スキーマ駆動の変換が、文書の外から受け取るリンクの引き先と Issue の URL。"""

    links: Mapping[str, DocumentLink]
    issue_url: str | None
    path: str
    # 同じ文書のテーブルの `title` から見出し（`x-key` の値）。外部キーのリンクのアンカーに使う
    anchors: Mapping[str, str] = field(default_factory=dict)
    # 同じ文書のテーブルの物理名か論理名から論理名。外部キーのリンクで `anchors` を引く前に論理名にする
    table_titles: Mapping[str, str] = field(default_factory=dict)
    # 文書の ID と項目のパスから、リンク先の文書でその項目が出す見出し。参照と本文の id のリンクのアンカーに使う
    item_heading: Callable[[str, str], str | None] = field(default=lambda document_id, item: None)
