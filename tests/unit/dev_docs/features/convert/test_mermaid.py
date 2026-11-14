from __future__ import annotations

from dev_docs.features.convert.mermaid import parse_mermaid
from dev_docs.features.convert.types import FlowGraph, SequenceGraph


def test_parse_mermaid() -> None:
    """フローチャート（正常系）。"""
    # 準備
    code = "flowchart LR\n  a[受け取り] -->|本文| b{分類}\n  b --> c[(控え)]"
    # 実行
    result = parse_mermaid(code)
    # 検証
    assert isinstance(result, FlowGraph)
    assert result.direction == "LR"
    assert [(n.id, n.kind, n.name) for n in result.nodes] == [
        ("a", "script", "受け取り"),
        ("b", "dm", "分類"),
        ("c", "data", "控え"),
    ]
    assert [(e.source, e.target, e.label) for e in result.edges] == [
        ("a", "b", "本文"),
        ("b", "c", None),
    ]


def test_parse_mermaid_when_chain() -> None:
    """線の連なりとラベルの記載方法（正常系）。"""
    # 準備
    code = "graph TD\n  a -- はい --> b --> c"
    # 実行
    result = parse_mermaid(code)
    # 検証
    assert isinstance(result, FlowGraph)
    assert [(e.source, e.target, e.label) for e in result.edges] == [
        ("a", "b", "はい"),
        ("b", "c", None),
    ]
    assert [n.name for n in result.nodes] == ["a", "b", "c"]


def test_parse_mermaid_when_sequence() -> None:
    """シーケンス図（正常系）。"""
    # 準備
    code = (
        "sequenceDiagram\n"
        "  actor U as 利用者\n"
        "  participant S as 画面\n"
        "  U->>+S: 開く\n"
        "  S-->>-U: 本文\n"
        "  S->>DB: 読む"
    )
    # 実行
    result = parse_mermaid(code)
    # 検証
    assert isinstance(result, SequenceGraph)
    assert [(p.id, p.kind, p.name) for p in result.participants] == [
        ("U", "external", "利用者"),
        ("S", "script", "画面"),
        ("DB", "script", "DB"),
    ]
    assert [(m.source, m.target, m.label, m.reply) for m in result.messages] == [
        ("U", "S", "開く", False),
        ("S", "U", "本文", True),
        ("S", "DB", "読む", False),
    ]


def test_parse_mermaid_when_unreadable_line() -> None:
    """読み取れない行（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  A->>B: 読む\n  alt 成功\n  B-->>A: 返す\n  end"
    # 実行
    result = parse_mermaid(code)
    # 検証
    assert result is None


def test_parse_mermaid_when_empty() -> None:
    """ノード・メッセージが無い（正常系）。"""
    # 実行
    sequence = parse_mermaid("sequenceDiagram\n  participant A")
    flow = parse_mermaid("flowchart TD")
    # 検証
    assert sequence is None
    assert flow is None


def test_parse_mermaid_when_other_diagram() -> None:
    """部品の無い図（正常系）。"""
    # 実行
    result = parse_mermaid("classDiagram\n  class A")
    # 検証
    assert result is None
