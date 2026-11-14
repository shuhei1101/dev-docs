from __future__ import annotations

import json
import re
from typing import Any

import pytest

from dev_docs.features.convert.diagrams import er_table_titles, render_diagram, render_mermaid
from dev_docs.features.convert.types import DiagramHead

HEAD = DiagramHead(title="図", scope="文書", updated="2026-11-03")


def _mermaid(block: str) -> list[str]:
    """map の範囲から Mermaid の行（前後の空白を除く）を取り出す。"""
    match = re.search(r"```mermaid\n(.*?)\n```", block, re.S)
    assert match is not None, block
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def _map_data(block: str) -> dict[str, Any] | None:
    """map の範囲から補足の JSON を取り出す（無ければ `None`）。"""
    match = re.search(r"<!-- map-data: (\{.*?\}) -->", block, re.S)
    if match is None:
        return None
    data: dict[str, Any] = json.loads(match.group(1))
    return data


def test_render_diagram() -> None:
    """フローチャート（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "label": "x"}],
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    assert result.startswith('<!-- map: {"title": "図"} -->')
    assert result.endswith("<!-- /map -->")
    lines = _mermaid(result)
    assert lines[0] == "flowchart TD"
    assert 'a["A"]:::script' in lines
    assert 'b["B"]:::script' in lines
    assert 'a -->|"x"| b' in lines
    assert "<!-- map-data" not in result


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        pytest.param("actor", "external", id="actor"),
        pytest.param("external", "external", id="external"),
        pytest.param("process", "script", id="process"),
        pytest.param("system", "script", id="system"),
        pytest.param("store", "data", id="store"),
        pytest.param("start", "start", id="start"),
        pytest.param("question", "question", id="question"),
        pytest.param("action", "action", id="action"),
        pytest.param("result", "result", id="result"),
        pytest.param(None, "script", id="none"),
    ],
)
def test_render_diagram_when_node_kinds(kind: str | None, expected: str) -> None:
    """ノードの種類（正常系）。"""
    # 準備
    node: dict[str, Any] = {"id": "a"} if kind is None else {"id": "a", "kind": kind}
    # 実行
    result = render_diagram({"nodes": [node], "edges": []}, "flowchart", HEAD)
    # 検証
    assert f'a["a"]:::{expected}' in _mermaid(result)


def test_render_diagram_when_hint_and_tip() -> None:
    """ノードの説明と線の種類・詳細（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a", "hint": "説明"}, {"id": "b"}],
        "edges": [{"from": "a", "to": "b", "label": "読む", "line": "read", "tip": "詳細"}],
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    data = _map_data(result)
    assert data is not None
    assert data["version"] == 1
    assert data["notes"]["a"]["text"] == "説明"
    assert data["notes"]["a->b"]["text"] == "詳細"
    assert data["layout"]["a->b"]["line"] == "read"


def test_render_diagram_when_unknown_line() -> None:
    """`LINE_KINDS` に無い線の種類（正常系）。"""
    # 準備
    value = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"from": "a", "to": "b", "line": "dotted"}]}
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    assert _map_data(result) is None


@pytest.mark.parametrize(
    ("kind", "value", "expected"),
    [
        pytest.param("flowchart", {}, "flowchart TD", id="flowchart"),
        pytest.param("dataflow", {}, "flowchart LR", id="dataflow"),
        pytest.param("architecture", {}, "flowchart LR", id="architecture"),
        pytest.param("dataflow", {"direction": "TD"}, "flowchart TD", id="dataflow-td"),
    ],
)
def test_render_diagram_when_direction(kind: str, value: dict[str, Any], expected: str) -> None:
    """向きの既定と指定（正常系）。"""
    # 準備
    graph = {**value, "nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"from": "a", "to": "b"}]}
    # 実行
    result = render_diagram(graph, kind, HEAD)  # type: ignore[arg-type]
    # 検証
    assert _mermaid(result)[0] == expected


def test_render_diagram_when_frame() -> None:
    """枠（正常系）。"""
    # 準備
    value = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [],
        "frame": {"label": "判定", "nodes": ["a", "b"]},
    }
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    lines = _mermaid(result)
    start = lines.index('subgraph frame ["判定"]')
    end = lines.index("end", start)
    assert lines[start + 1 : end] == ['a["a"]:::script', 'b["b"]:::script']
    assert 'c["c"]:::script' in lines


def test_render_diagram_when_state() -> None:
    """状態遷移（正常系）。"""
    # 準備
    value = {
        "states": [{"name": "下書き"}, {"name": "公開"}],
        "initial": "下書き",
        "final": ["公開"],
        "transitions": [
            {"from": "下書き", "to": "公開", "trigger": "公開する", "condition": "承認済み"}
        ],
    }
    # 実行
    result = render_diagram(value, "state", HEAD)
    # 検証
    lines = _mermaid(result)
    assert lines[0] == "stateDiagram-v2"
    assert 'state "下書き" as s1' in lines
    assert 'state "公開" as s2' in lines
    assert "[*] --> s1" in lines
    assert "s1 --> s2 : 公開する [承認済み]" in lines
    assert "s2 --> [*]" in lines


def test_render_diagram_when_state_representative() -> None:
    """全状態と元の状態（正常系）。"""
    # 準備
    value = {
        "states": [{"name": "編集中"}, {"name": "中断"}],
        "representative": "編集中",
        "transitions": [
            {"from": "全状態", "to": "中断"},
            {"from": "中断", "to": "元の状態"},
        ],
    }
    # 実行
    result = render_diagram(value, "state", HEAD)
    # 検証
    lines = _mermaid(result)
    assert "s1 --> s2" in lines
    assert "s2 --> s1" in lines
    assert "全状態" not in result.split("```mermaid")[1]


def test_render_diagram_when_state_without_representative() -> None:
    """代表の状態が無い（正常系）。"""
    # 準備
    value = {"states": [{"name": "下書き"}], "transitions": [{"from": "全状態", "to": "下書き"}]}
    # 実行
    result = render_diagram(value, "state", HEAD)
    # 検証
    assert _mermaid(result) == ["stateDiagram-v2", 'state "下書き" as s1']


def test_render_diagram_when_er() -> None:
    """ER 図（正常系）。"""
    # 準備
    value = {
        "entities": [
            {"name": "顧客"},
            {
                "name": "注文",
                "columns": [
                    {"name": "id", "type": "int", "key": "PK"},
                    {"name": "customer_id", "type": "int", "key": "FK"},
                ],
            },
        ],
        "relations": [
            {
                "from": "顧客",
                "from_column": "id",
                "from_cardinality": "1",
                "to": "注文",
                "to_column": "customer_id",
                "to_cardinality": "0..n",
                "label": "注文する",
            }
        ],
    }
    tables = [
        {
            "name": "customers",
            "title": "顧客",
            "columns": [{"name": "id", "primary_key": True}, {"name": "email"}],
        }
    ]
    # 実行
    result = render_diagram(value, "er", HEAD, tables=tables)
    # 検証
    lines = _mermaid(result)
    assert lines[0] == "erDiagram"
    assert "any id PK" in lines
    assert "any email" in lines
    assert 'int customer_id FK "参照: 顧客.id"' in lines
    assert '顧客 ||--o{ 注文 : "注文する"' in lines


def test_render_diagram_when_er_relation_dropped() -> None:
    """端の列か多重度が描けない関連（正常系）。"""
    # 準備
    value = {
        "entities": [
            {"name": "顧客", "columns": [{"name": "id", "key": "PK"}]},
            {"name": "注文", "columns": [{"name": "id", "key": "PK"}]},
        ],
        "relations": [
            {
                "from": "顧客",
                "from_column": "id",
                "from_cardinality": "1",
                "to": "注文",
                "to_column": "customer_id",
                "to_cardinality": "0..n",
            },
            {
                "from": "顧客",
                "from_column": "id",
                "from_cardinality": "many",
                "to": "注文",
                "to_column": "id",
                "to_cardinality": "1",
            },
        ],
    }
    # 実行
    result = render_diagram(value, "er", HEAD)
    # 検証
    assert _mermaid(result) == ["erDiagram", "顧客 {", "any id PK", "}", "注文 {", "any id PK", "}"]
    assert "参照:" not in result


def test_render_diagram_when_marker_text() -> None:
    """HTML のコメントと Mermaid の文字列を閉じる文字（正常系）。"""
    # 準備
    value = {"nodes": [{"id": "a", "label": '"x"', "hint": "a--b"}], "edges": []}
    # 実行
    result = render_diagram(value, "flowchart", HEAD)
    # 検証
    marker = re.search(r"<!-- map-data: (.*?) -->", result, re.S)
    assert marker is not None
    assert "--" not in marker.group(1)
    data = _map_data(result)
    assert data is not None
    assert data["notes"]["a"]["text"] == "a- -b"
    assert 'a["#quot;x#quot;"]:::script' in _mermaid(result)


def test_render_diagram_when_unknown_kind() -> None:
    """知らない図の種類（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match="x-diagram gantt は描けません"):
        render_diagram({}, "gantt", HEAD)  # type: ignore[arg-type]


def test_er_table_titles() -> None:
    """物理名と論理名（正常系）。"""
    # 準備
    tables = [
        {"name": "customers", "title": "顧客"},
        {"name": "payments", "title": "支払い"},
    ]
    # 実行
    result = er_table_titles(tables)
    # 検証
    assert result == {"customers": "顧客", "顧客": "顧客", "payments": "支払い", "支払い": "支払い"}


def test_er_table_titles_when_duplicated_or_untitled() -> None:
    """重なるキーと論理名の無いテーブル（正常系）。"""
    # 準備
    tables = [{"name": "a", "title": "A"}, {"name": "A", "title": "B"}, {"name": "c"}]
    # 実行
    result = er_table_titles(tables)
    # 検証
    assert result["A"] == "A"
    assert "c" not in result


def test_render_mermaid() -> None:
    """シーケンス図（正常系）。"""
    # 準備
    code = "sequenceDiagram\n  A->>B: 読む"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    assert result.startswith('<!-- map: {"title": "図"} -->')
    assert f"```mermaid\n{code}\n```" in result
    assert result.endswith("<!-- /map -->")


@pytest.mark.parametrize(
    "first",
    [
        pytest.param("flowchart TD", id="flowchart"),
        pytest.param("graph LR", id="graph"),
        pytest.param("erDiagram", id="er"),
        pytest.param("stateDiagram-v2", id="state-v2"),
        pytest.param("stateDiagram", id="state"),
    ],
)
def test_render_mermaid_when_kinds(first: str) -> None:
    """map で描く種類（正常系）。"""
    # 実行
    result = render_mermaid(f"{first}\n  a --> b", HEAD)
    # 検証
    assert result.startswith("<!-- map: ")


def test_render_mermaid_when_not_mappable() -> None:
    """map で描かない種類（正常系）。"""
    # 準備
    code = "classDiagram\n  class A"
    # 実行
    result = render_mermaid(code, HEAD)
    # 検証
    assert result == f"```mermaid\n{code}\n```"
