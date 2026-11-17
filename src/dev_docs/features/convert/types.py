"""変換の結果・図の見出し・描画の文脈の型。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

type Shape = Literal["body", "table", "sections", "list", "diagram", "attributes"]
type DiagramKind = Literal["flowchart", "dataflow", "architecture", "state", "er"]


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
    """画面へ返却する Markdown か、変換の失敗。"""

    markdown: str
    table_keys: list[str] = field(default_factory=list)
    failure: ConvertFailure | None = None


@dataclass(frozen=True)
class DiagramHead:
    """map の範囲の `title` にする題名と、図の元データの表が使用する範囲・更新日。"""

    title: str
    scope: str
    updated: str


@dataclass(frozen=True)
class ItemHeading:
    """文書の項目のパスが指す、スキーマ駆動の変換が出す見出しと、その見出しを配置する組み立てのパス。"""

    text: str
    # 名前は `.` で、配列の要素は `[{位置}]`（0 始まり）で繋いだ値のパス。見出しのアンカーの一覧のキー
    path: str


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
    # 同じ文書のテーブルの `title` から見出し（`x-key` の値）。外部キーのリンクのアンカーに使用する
    anchors: Mapping[str, str] = field(default_factory=dict)
    # 同じ文書のテーブルの物理名か論理名から論理名。外部キーのリンクで `anchors` を検索する前に論理名にする
    table_titles: Mapping[str, str] = field(default_factory=dict)
    # 文書の ID と項目のパスから、リンク先の文書でその項目が出す見出しのアンカー。参照と本文の id のリンクに使用する
    item_anchor: Callable[[str, str], str | None] = field(default=lambda document_id, item: None)
    # 検討事項の文書を探した結果の ID。`decisions` の値のうち、この ID だけを検討事項の文書へのリンクにする
    decisions: frozenset[str] = field(default_factory=frozenset)
